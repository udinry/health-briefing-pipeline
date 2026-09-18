"""Generate the iOS Shortcuts that push Apple Health data to the ingest endpoint.

Usage:
    python3 gen_shortcut.py <config.env> <output-dir>

config.env needs one line:
    INGEST_URL=https://<your-app>.vercel.app/api/ingest

No secret goes in the config or in the generated files. Each generated shortcut
that talks to the server asks for the MCP secret when it is imported on the
iPhone, and stores it in the shortcut on that device only.

Then sign each file on macOS so iOS will accept it:
    shortcuts sign --mode anyone --input "Health Sync.shortcut" \
                                 --output "Health Sync.signed.shortcut"

Files produced:
    Health Sync        3 days per run, silent. This is the one to automate.
    Health Check       1 day, shows the values found and the server's reply.
    Health Backfill    30 days, for first setup or after a long outage.
    Sleep Diagnostic   read-only; reports what sleep data Health actually holds.
"""

import plistlib, uuid, sys, os, re

FMT = "yyyy-MM-dd HH:mm:ss Z"

# Sleep stage labels, in the order they are summed. Apple has renamed these
# between OS releases; Sleep Diagnostic reports which ones match on a device.
# (Health label, shortcut variable, metric name stored on the server)
SLEEP_STAGES = [("Deep", "SleepDeep", "sleep_deep"),
                ("REM", "SleepREM", "sleep_rem"),
                ("Core", "SleepCore", "sleep_core"),
                ("Asleep", "SleepUnspec", "sleep_unspecified")]

# Daily quantity metrics: (Health type, statistic, variable, json name, units)
DAILY_METRICS = [
    ("Steps",                  "Sum",     "Steps",  "step_count",             "count"),
    ("Active Calories",        "Sum",     "Energy", "active_energy",          "kcal"),
    ("Resting Heart Rate",     "Average", "RHR",    "resting_heart_rate",     "bpm"),
    ("Heart Rate Variability", "Average", "HRV",    "heart_rate_variability", "ms"),
]


def U():
    return str(uuid.uuid4()).upper()


# ---------- attachment / token helpers ----------
def var(name, prop=None):
    v = {"Type": "Variable", "VariableName": name}
    if prop:
        v["Aggrandizements"] = [{"Type": "WFPropertyVariableAggrandizement", "PropertyName": prop}]
    return v


def out(uid, name):
    return {"Type": "ActionOutput", "OutputUUID": uid, "OutputName": name}


def att(v):
    return {"Value": v, "WFSerializationType": "WFTextTokenAttachment"}


def tok(*parts):
    """parts: str or attachment-value dict -> WFTextTokenString"""
    s, ranges = "", {}
    for p in parts:
        if isinstance(p, str):
            s += p
        else:
            ranges["{%d, 1}" % len(s)] = p
            s += "￼"
    return {"Value": {"string": s, "attachmentsByRange": ranges},
            "WFSerializationType": "WFTextTokenString"}


def tokjson(template, mapping):
    """Split a template on PLACEHOLDER tokens and substitute attachments."""
    parts = re.split(r'(%s)' % '|'.join(map(re.escape, mapping)), template)
    return tok(*[mapping[p] if p in mapping else p for p in parts if p != ""])


class Builder:
    """Accumulates actions for one shortcut."""

    def __init__(self):
        self.actions = []
        self.import_questions = []

    # --- core ---
    def A(self, ident, params, uid=None):
        p = dict(params)
        if uid:
            p["UUID"] = uid
        self.actions.append({"WFWorkflowActionIdentifier": "is.workflow.actions." + ident,
                             "WFWorkflowActionParameters": p})
        return uid

    def setvar(self, name, value):
        self.A("setvariable", {"WFVariableName": name, "WFInput": att(value)})

    def text(self, *parts):
        u = U()
        self.A("gettext", {"WFTextActionText": tok(*parts)}, u)
        return out(u, "Text")

    def ask_on_import(self, prompt, default=""):
        """A Text action whose content iOS asks for when the shortcut is imported."""
        u = U()
        self.A("gettext", {"WFTextActionText": default}, u)
        self.import_questions.append({
            "ParameterKey": "WFTextActionText",
            "Category": "Parameter",
            "ActionIndex": len(self.actions) - 1,
            "Text": prompt,
            "DefaultValue": default,
        })
        return out(u, "Text")

    # --- dates ---
    def date_now(self):
        u = U()
        self.A("date", {"WFDateActionMode": "Current Date"}, u)
        return out(u, "Date")

    def adjust(self, date_v, op, mag=None, unit=None):
        u = U()
        p = {"WFDate": tok(date_v), "WFAdjustOperation": op}
        if mag is not None:
            p["WFDuration"] = {"Value": {"Magnitude": mag, "Unit": unit},
                               "WFSerializationType": "WFQuantityFieldValue"}
        self.A("adjustdate", p, u)
        return out(u, "Adjusted Date")

    def fmt_date(self, date_v):
        u = U()
        self.A("format.date", {"WFDateFormatStyle": "Custom", "WFDateFormat": FMT,
                               "WFDate": tok(date_v)}, u)
        return out(u, "Formatted Date")

    # --- health ---
    def find_health(self, htype, rows, group_by=None):
        u = U()
        p = {"WFContentItemFilter": {
                "Value": {"WFActionParameterFilterPrefix": 1,
                          "WFActionParameterFilterTemplates": [enum_row("Type", htype, removable=False)] + rows,
                          "WFContentPredicateBoundedDate": False},
                "WFSerializationType": "WFContentPredicateTableTemplate"},
             "WFContentItemSortProperty": "Start Date", "WFContentItemSortOrder": "Oldest First",
             "WFContentItemLimitEnabled": False, "WFHKSampleFilteringFillMissing": False}
        if group_by:
            p["WFHKSampleFilteringGroupBy"] = group_by
        self.A("filter.health.quantity", p, u)
        return out(u, "Health Samples")

    def details(self, inp, prop):
        u = U()
        self.A("properties.health.quantity", {"WFInput": att(inp), "WFContentItemPropertyName": prop}, u)
        return out(u, prop)

    def stats(self, inp, op):
        u = U()
        self.A("statistics", {"WFStatisticsOperation": op, "Input": att(inp)}, u)
        return out(u, "Statistics")

    def count(self, inp):
        u = U()
        self.A("count", {"WFCountType": "Items", "Input": att(inp)}, u)
        return out(u, "Count")

    def guarded(self, inp, op, vname, via_duration=False):
        """vname = "" first; only if the find returned samples, vname = stat(...).

        Without this, a day with no samples aborts the whole run.
        """
        self.setvar(vname, self.text(""))
        g = U()
        self.A("conditional", {"WFControlFlowMode": 0, "GroupingIdentifier": g,
                               "WFCondition": 100,
                               "WFInput": {"Type": "Variable", "Variable": att(inp)}})
        self.setvar(vname, self.stats(self.details(inp, "Duration") if via_duration else inp, op))
        self.A("conditional", {"WFControlFlowMode": 2, "GroupingIdentifier": g}, U())

    def show(self, *parts):
        self.A("showresult", {"Text": tok(*parts)})


# ---------- filter rows ----------
def enum_row(prop, value, op=4, removable=True):
    return {"Bounded": True, "Operator": op, "Property": prop, "Removable": removable,
            "Values": {"Enumeration": {"Value": value, "WFSerializationType": "WFStringSubstitutableState"}}}


def str_row(prop, value, op=4):
    """Sleep stage values are matched as plain strings, not enumerations."""
    return {"Bounded": True, "Operator": op, "Property": prop, "Removable": True,
            "Values": {"Unit": 4, "String": value}}


def between_row(prop, a, b):
    """Operator 1003 is 'is between'."""
    return {"Bounded": True, "Operator": 1003, "Property": prop, "Removable": True,
            "Values": {"Date": att(a), "AnotherDate": att(b), "Unit": 16, "Number": "1"}}


META = {
    "WFWorkflowClientVersion": "2607.0.3",
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59764},
    "WFWorkflowTypes": [],
    "WFWorkflowHasShortcutInputVariables": False,
    "WFWorkflowInputContentItemClasses": [
        "WFAppStoreAppContentItem", "WFArticleContentItem", "WFContactContentItem",
        "WFDateContentItem", "WFEmailAddressContentItem", "WFGenericFileContentItem",
        "WFImageContentItem", "WFiTunesProductContentItem", "WFLocationContentItem",
        "WFDCMapsLinkContentItem", "WFAVAssetContentItem", "WFPDFContentItem",
        "WFPhoneNumberContentItem", "WFRichTextContentItem", "WFSafariWebPageContentItem",
        "WFStringContentItem", "WFURLContentItem"],
}


def wrap(b, name):
    d = dict(META)
    d["WFWorkflowActions"] = b.actions
    d["WFWorkflowImportQuestions"] = b.import_questions
    d["WFWorkflowName"] = name
    return d


# ---------- the sync shortcut ----------
def build_sync(ingest_url, days, show_result, name):
    b = Builder()

    secret = b.ask_on_import(
        "Paste your MCP_SECRET (the same secret you enter on the server's authorize page)")
    b.setvar("Secret", secret)

    b.setvar("Cursor", b.date_now())
    g = U()
    b.A("repeat.count", {"WFControlFlowMode": 0, "GroupingIdentifier": g, "WFRepeatCount": days})

    # Step the cursor back one day per iteration. The magnitude must be a plain
    # number: a variable here silently resolves to zero.
    b.setvar("Cursor", b.adjust(var("Cursor"), "Subtract", "1", "days"))
    b.setvar("DayStart", b.adjust(var("Cursor"), "Get Start of Day"))
    b.setvar("DayEnd", b.adjust(var("DayStart"), "Add", "1", "days"))
    b.setvar("SleepStart", b.adjust(var("DayStart"), "Add", "18", "hr"))
    b.setvar("SleepEnd", b.adjust(var("DayStart"), "Add", "36", "hr"))
    b.setvar("Stamp", b.fmt_date(var("DayStart")))

    day = lambda: [between_row("Start Date", var("DayStart"), var("DayEnd"))]
    night = lambda: [between_row("Start Date", var("SleepStart"), var("SleepEnd"))]

    for htype, op, vname, _, _ in DAILY_METRICS:
        b.guarded(b.find_health(htype, day(), "Day"), op, vname)

    # Heart rate: averaged over the raw samples, so the day and night windows differ.
    b.guarded(b.find_health("Heart Rate", day()), "Average", "HRDay")
    b.guarded(b.find_health("Heart Rate", night()), "Average", "HRNight")

    # Sleep samples carry a text value, so sum each stage's Duration (seconds).
    for stage, vname, _ in SLEEP_STAGES:
        b.guarded(b.find_health("Sleep", night() + [str_row("Value", stage)]), "Sum", vname, via_duration=True)

    # Workouts
    wk = b.find_health("Workouts", day())
    g2 = U()
    b.A("repeat.each", {"WFControlFlowMode": 0, "GroupingIdentifier": g2, "WFInput": att(wk)})
    ws, we = b.fmt_date(var("Repeat Item", "Start Date")), b.fmt_date(var("Repeat Item", "End Date"))
    b.A("gettext", {"WFTextActionText": tokjson(
        '{"id":"wk-START","name":"TYPE","start":"START","end":"END","value":"VALUE",'
        '"duration_text":"DUR","source":"Shortcuts"}',
        {"START": ws, "END": we, "TYPE": var("Repeat Item", "Name"),
         "VALUE": var("Repeat Item", "Value"), "DUR": var("Repeat Item", "Duration")})}, U())
    end2 = U()
    b.A("repeat.each", {"WFControlFlowMode": 2, "GroupingIdentifier": g2}, end2)
    cu = U()
    b.A("text.combine", {"text": att(out(end2, "Repeat Results")),
                         "WFTextSeparator": "Custom", "WFTextCustomSeparator": ","}, cu)
    b.setvar("Workouts", out(cu, "Combined Text"))

    # Body: Health Auto Export shape, every number as a string.
    def m(jname, units, placeholder):
        return ('{"name":"%s","units":"%s","data":[{"date":"STAMP","qty":"%s","source":"Shortcuts"}]}'
                % (jname, units, placeholder))

    metrics = [m(jname, units, ph) for _, _, ph, jname, units in DAILY_METRICS]
    metrics += [m("heart_rate_day_avg", "bpm", "HRDay"), m("heart_rate_sleep_avg", "bpm", "HRNight")]
    metrics += [m(jname, "s", vname) for _, vname, jname in SLEEP_STAGES]
    body = '{"data":{"metrics":[' + ",".join(metrics) + '],"workouts":[WORKOUTS]}}'

    mapping = {"STAMP": var("Stamp"), "WORKOUTS": var("Workouts")}
    for _, _, ph, _, _ in DAILY_METRICS:
        mapping[ph] = var(ph)
    mapping["HRDay"], mapping["HRNight"] = var("HRDay"), var("HRNight")
    for _, vname, _ in SLEEP_STAGES:
        mapping[vname] = var(vname)

    tu = U()
    b.A("gettext", {"WFTextActionText": tokjson(body, mapping)}, tu)

    ru = U()
    b.A("downloadurl", {
        "WFURL": ingest_url, "WFHTTPMethod": "POST", "ShowHeaders": True,
        "WFHTTPHeaders": {"Value": {"WFDictionaryFieldValueItems": [
            {"WFKey": tok("Authorization"), "WFItemType": 0, "WFValue": tok("Bearer ", var("Secret"))},
            {"WFKey": tok("Content-Type"), "WFItemType": 0, "WFValue": tok("application/json")}]},
            "WFSerializationType": "WFDictionaryFieldValue"},
        "WFHTTPBodyType": "File", "WFRequestVariable": att(out(tu, "Text"))}, ru)
    b.setvar("LastResponse", out(ru, "Contents of URL"))
    b.A("repeat.count", {"WFControlFlowMode": 2, "GroupingIdentifier": g}, U())

    if show_result:
        b.show("Synced ", str(days), " day(s).\nLast day: ", var("Stamp"),
               "\nsteps=", var("Steps"), " kcal=", var("Energy"),
               "\nhr day=", var("HRDay"), " night=", var("HRNight"),
               "\nsleep(s) deep=", var("SleepDeep"), " rem=", var("SleepREM"),
               " core=", var("SleepCore"), " unspec=", var("SleepUnspec"),
               "\nserver: ", var("LastResponse"))
    return wrap(b, name)


# ---------- the sleep diagnostic ----------
def build_sleep_diagnostic(name):
    """Read-only. Reports what sleep data Health holds and which labels match."""
    b = Builder()

    b.setvar("Now", b.date_now())
    b.setvar("Yesterday", b.adjust(var("Now"), "Subtract", "1", "days"))
    b.setvar("DayStart", b.adjust(var("Yesterday"), "Get Start of Day"))
    b.setvar("SleepStart", b.adjust(var("DayStart"), "Add", "18", "hr"))
    b.setvar("SleepEnd", b.adjust(var("DayStart"), "Add", "36", "hr"))
    b.setvar("Fortnight", b.adjust(var("Now"), "Subtract", "14", "days"))

    night = [between_row("Start Date", var("SleepStart"), var("SleepEnd"))]
    recent = [between_row("Start Date", var("Fortnight"), var("Now"))]

    lines = []

    # Control: does Health return anything at all through Shortcuts?
    b.setvar("StepsN", b.count(b.find_health("Steps", recent)))
    lines += ["steps samples (14d): ", var("StepsN"), "\n"]

    # Does the type name still resolve, and is there any sleep at all?
    sleep_recent = b.find_health("Sleep", recent)
    b.setvar("SleepN", b.count(sleep_recent))
    lines += ["type 'Sleep' (14d): ", var("SleepN"), "\n"]

    b.setvar("SleepAnalysisN", b.count(b.find_health("Sleep Analysis", recent)))
    lines += ["type 'Sleep Analysis' (14d): ", var("SleepAnalysisN"), "\n"]

    sleep_night = b.find_health("Sleep", night)
    b.setvar("NightN", b.count(sleep_night))
    lines += ["last night 18:00-12:00: ", var("NightN"), "\n"]

    # Which stage labels match?
    for stage in ["Deep", "REM", "Core", "Asleep", "In Bed", "Awake"]:
        vname = "N" + stage.replace(" ", "")
        b.setvar(vname, b.count(b.find_health("Sleep", recent + [str_row("Value", stage)])))
        lines += [stage, "=", var(vname), "  "]
    lines += ["\n"]

    # The labels Health actually uses, straight from last night's samples.
    vals = b.details(sleep_night, "Value")
    cu = U()
    b.A("text.combine", {"text": att(vals), "WFTextSeparator": "Custom", "WFTextCustomSeparator": ", "}, cu)
    b.setvar("Values", out(cu, "Combined Text"))
    lines += ["values seen last night:\n", var("Values")]

    b.show("SLEEP DIAGNOSTIC\n", *lines)
    return wrap(b, name)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    cfg = dict(re.findall(r'^([A-Z_]+)=(.*)$', open(sys.argv[1]).read(), re.M))
    ingest = cfg.get("INGEST_URL", "").strip()
    if not ingest:
        sys.exit("INGEST_URL missing from config")
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    files = {
        "Health Sync": build_sync(ingest, 3, False, "Health Sync"),
        "Health Check": build_sync(ingest, 1, True, "Health Check"),
        "Health Backfill": build_sync(ingest, 30, True, "Health Backfill"),
        "Sleep Diagnostic": build_sleep_diagnostic("Sleep Diagnostic"),
    }
    for name, doc in files.items():
        path = os.path.join(outdir, name + ".shortcut")
        with open(path, "wb") as f:
            plistlib.dump(doc, f, fmt=plistlib.FMT_BINARY)
        print("wrote %s (%d actions)" % (path, len(doc["WFWorkflowActions"])))


if __name__ == "__main__":
    main()
