"""Structural tests for the generated shortcuts.

These cannot prove a shortcut works on a phone, but they catch every mistake
that has actually broken this pipeline before: an unbalanced control-flow
block, a variable used before it is set, a secret baked into the file, a
sleep stage summed as a value instead of a duration.

Run: python3 -m unittest discover -s shortcut/tests
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gen_shortcut as G  # noqa: E402

INGEST = "https://example.vercel.app/api/ingest"


def ids(doc):
    return [a["WFWorkflowActionIdentifier"] for a in doc["WFWorkflowActions"]]


def flow_balance(doc, ident):
    """Control-flow actions: mode 0 opens, 1 is an else branch, 2 closes."""
    opens = closes = 0
    for a in doc["WFWorkflowActions"]:
        if a["WFWorkflowActionIdentifier"] == ident:
            mode = a["WFWorkflowActionParameters"].get("WFControlFlowMode")
            opens += mode == 0
            closes += mode == 2
    return opens, closes


def walk_attachments(obj):
    """Yield every attachment dict anywhere in the document."""
    if isinstance(obj, dict):
        if obj.get("Type") in ("Variable", "ActionOutput"):
            yield obj
        for v in obj.values():
            yield from walk_attachments(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_attachments(v)


def filter_rows(doc):
    for a in doc["WFWorkflowActions"]:
        if a["WFWorkflowActionIdentifier"].endswith("filter.health.quantity"):
            f = a["WFWorkflowActionParameters"]["WFContentItemFilter"]["Value"]
            yield a, f["WFActionParameterFilterTemplates"]


class SyncShortcut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = G.build_sync(INGEST, 3, False, "Health Sync")
        cls.check = G.build_sync(INGEST, 1, True, "Health Check")

    def test_control_flow_is_balanced(self):
        for ident in ("is.workflow.actions.conditional", "is.workflow.actions.repeat.count",
                      "is.workflow.actions.repeat.each"):
            opens, closes = flow_balance(self.doc, ident)
            self.assertEqual(opens, closes, "%s unbalanced: %d open, %d close" % (ident, opens, closes))
            self.assertGreater(opens, 0, "%s missing" % ident)

    def test_every_statistic_is_guarded(self):
        """A day with no samples must not abort the run."""
        conditionals, _ = flow_balance(self.doc, "is.workflow.actions.conditional")
        stats = ids(self.doc).count("is.workflow.actions.statistics")
        self.assertEqual(stats, conditionals,
                         "%d statistics but %d guards" % (stats, conditionals))

    def test_variables_are_set_before_use(self):
        assigned, seen_first_use = set(), {}
        for a in self.doc["WFWorkflowActions"]:
            params = a["WFWorkflowActionParameters"]
            for att in walk_attachments(params):
                name = att.get("VariableName")
                if name and name not in assigned and name not in ("Repeat Item", "Repeat Index"):
                    seen_first_use.setdefault(name, True)
            if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.setvariable":
                assigned.add(params["WFVariableName"])
        self.assertEqual(seen_first_use, {}, "used before set: %s" % sorted(seen_first_use))

    def test_no_secret_material_in_file(self):
        blob = repr(self.doc)
        self.assertNotRegex(blob, r"[0-9a-f]{32,}", "looks like a secret is embedded")
        self.assertIn("Bearer ", blob)

    def test_secret_is_asked_for_on_import(self):
        qs = self.doc["WFWorkflowImportQuestions"]
        self.assertEqual(len(qs), 1)
        q = qs[0]
        self.assertEqual(q["ParameterKey"], "WFTextActionText")
        target = self.doc["WFWorkflowActions"][q["ActionIndex"]]
        self.assertEqual(target["WFWorkflowActionIdentifier"], "is.workflow.actions.gettext")

    def test_sleep_stages_sum_durations_not_values(self):
        stages = [r["Values"]["String"]
                  for _, rows in filter_rows(self.doc) for r in rows
                  if r["Property"] == "Value"]
        self.assertEqual(stages, [s for s, _, _ in G.SLEEP_STAGES])
        self.assertIn("is.workflow.actions.properties.health.quantity", ids(self.doc))
        for a in self.doc["WFWorkflowActions"]:
            if a["WFWorkflowActionIdentifier"].endswith("properties.health.quantity"):
                self.assertEqual(a["WFWorkflowActionParameters"]["WFContentItemPropertyName"], "Duration")

    def test_stored_metric_names_never_drift(self):
        """Renaming a metric silently splits its history in the database."""
        self.assertEqual([j for _, _, j in G.SLEEP_STAGES],
                         ["sleep_deep", "sleep_rem", "sleep_core", "sleep_unspecified"])
        self.assertEqual([j for _, _, _, j, _ in G.DAILY_METRICS],
                         ["step_count", "active_energy", "resting_heart_rate", "heart_rate_variability"])

    def test_sample_counts_are_sent_with_the_values(self):
        """A null value plus a count tells "Health had nothing" apart from "the filter missed"."""
        self.assertEqual([j for _, j in G.DIAG_METRICS],
                         ["sleep_samples_n", "heart_rate_samples_n"])
        self.assertEqual(ids(self.doc).count("is.workflow.actions.count"), len(G.DIAG_METRICS))

    def test_body_carries_every_metric(self):
        texts = [a["WFWorkflowActionParameters"]["WFTextActionText"]
                 for a in self.doc["WFWorkflowActions"]
                 if a["WFWorkflowActionIdentifier"].endswith("gettext")
                 and isinstance(a["WFWorkflowActionParameters"].get("WFTextActionText"), dict)]
        body = max((t["Value"]["string"] for t in texts), key=len)
        for name in ("step_count", "active_energy", "resting_heart_rate", "heart_rate_variability",
                     "heart_rate_day_avg", "heart_rate_sleep_avg",
                     "sleep_deep", "sleep_rem", "sleep_core", "sleep_unspecified",
                     "sleep_samples_n", "heart_rate_samples_n"):
            self.assertIn('"name":"%s"' % name, body)

    def test_posts_to_the_configured_url(self):
        posts = [a["WFWorkflowActionParameters"] for a in self.doc["WFWorkflowActions"]
                 if a["WFWorkflowActionIdentifier"].endswith("downloadurl")]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["WFURL"], INGEST)
        self.assertEqual(posts[0]["WFHTTPMethod"], "POST")

    def test_sync_is_silent_and_check_reports(self):
        self.assertNotIn("is.workflow.actions.showresult", ids(self.doc))
        self.assertEqual(ids(self.check).count("is.workflow.actions.showresult"), 1)

    def test_day_offset_is_a_literal_number(self):
        """A variable magnitude in Adjust Date silently resolves to zero."""
        for a in self.doc["WFWorkflowActions"]:
            if a["WFWorkflowActionIdentifier"].endswith("adjustdate"):
                dur = a["WFWorkflowActionParameters"].get("WFDuration")
                if dur:
                    self.assertIsInstance(dur["Value"]["Magnitude"], str)
                    self.assertRegex(dur["Value"]["Magnitude"], r"^\d+$")


class SleepDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = G.build_sleep_diagnostic("Sleep Diagnostic")

    def test_is_read_only(self):
        self.assertNotIn("is.workflow.actions.downloadurl", ids(self.doc))
        self.assertEqual(self.doc["WFWorkflowImportQuestions"], [])

    def test_probes_both_type_names_and_every_stage_label(self):
        types = [r["Values"]["Enumeration"]["Value"]
                 for _, rows in filter_rows(self.doc) for r in rows if r["Property"] == "Type"]
        self.assertIn("Sleep", types)
        self.assertIn("Sleep Analysis", types)
        self.assertIn("Steps", types)
        labels = [r["Values"]["String"]
                  for _, rows in filter_rows(self.doc) for r in rows if r["Property"] == "Value"]
        self.assertEqual(sorted(labels), sorted(["Deep", "REM", "Core", "Asleep", "In Bed", "Awake"]))

    def test_reports_the_labels_health_actually_uses(self):
        props = [a["WFWorkflowActionParameters"]["WFContentItemPropertyName"]
                 for a in self.doc["WFWorkflowActions"]
                 if a["WFWorkflowActionIdentifier"].endswith("properties.health.quantity")]
        self.assertIn("Value", props)
        self.assertIn("is.workflow.actions.showresult", ids(self.doc))


class Serialization(unittest.TestCase):
    def test_attachment_ranges_match_placeholder_positions(self):
        t = G.tok("a=", G.var("X"), " b=", G.var("Y"))
        s, ranges = t["Value"]["string"], t["Value"]["attachmentsByRange"]
        for key, att in ranges.items():
            i = int(re.match(r"\{(\d+), 1\}", key).group(1))
            self.assertEqual(s[i], "￼")
        self.assertEqual(len(ranges), 2)

    def test_tokjson_substitutes_every_placeholder(self):
        t = G.tokjson('{"a":"AA","b":"BB"}', {"AA": G.var("A"), "BB": G.var("B")})
        self.assertEqual(t["Value"]["string"], '{"a":"￼","b":"￼"}')

    def test_between_row_uses_the_is_between_operator(self):
        r = G.between_row("Start Date", G.var("a"), G.var("b"))
        self.assertEqual(r["Operator"], 1003)
        self.assertEqual(r["Values"]["Unit"], 16)


if __name__ == "__main__":
    unittest.main()
