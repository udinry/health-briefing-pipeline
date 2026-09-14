import plistlib, uuid, sys, os, re

"""Generate iOS Shortcuts (.shortcut plists) that push Apple Health data to the ingest endpoint.

Usage:  python3 gen_shortcut.py <config.env> <output-dir>
config.env must contain:
  MCP_SECRET=<your shared secret>
  INGEST_URL=https://<your-app>.vercel.app/api/ingest
Then sign each file on macOS so iOS accepts it:
  shortcuts sign --mode anyone --input "Health Sync v7.shortcut" --output "Health Sync v7.signed.shortcut"
"""
_env = dict(re.findall(r'^([A-Z_]+)=(.*)$', open(sys.argv[1]).read(), re.M))
SECRET = _env["MCP_SECRET"].strip()
INGEST = _env.get("INGEST_URL", "").strip() or sys.exit("INGEST_URL missing from config")
FMT = "yyyy-MM-dd HH:mm:ss Z"
OUT = sys.argv[2]

def U(): return str(uuid.uuid4()).upper()

# ---------- attachment / token helpers ----------
def var(name, prop=None):
    v = {"Type": "Variable", "VariableName": name}
    if prop: v["Aggrandizements"] = [{"Type": "WFPropertyVariableAggrandizement", "PropertyName": prop}]
    return v
def out(uid, name): return {"Type": "ActionOutput", "OutputUUID": uid, "OutputName": name}
def att(v): return {"Value": v, "WFSerializationType": "WFTextTokenAttachment"}
def tok(*parts):
    """parts: str or attachment-value dict -> WFTextTokenString"""
    s, ranges = "", {}
    for p in parts:
        if isinstance(p, str): s += p
        else:
            ranges["{%d, 1}" % len(s)] = p; s += "￼"
    return {"Value": {"string": s, "attachmentsByRange": ranges}, "WFSerializationType": "WFTextTokenString"}
def tokjson(template, mapping):
    """Split template on PLACEHOLDER tokens and substitute attachments."""
    parts = re.split(r'(%s)' % '|'.join(map(re.escape, mapping)), template)
    return tok(*[mapping[p] if p in mapping else p for p in parts if p != ""])

actions = []
def A(ident, params, uid=None):
    p = dict(params)
    if uid: p["UUID"] = uid
    actions.append({"WFWorkflowActionIdentifier": "is.workflow.actions." + ident, "WFWorkflowActionParameters": p})
    return uid

def setvar(name, value): A("setvariable", {"WFVariableName": name, "WFInput": att(value)})
def date_now():
    u = U(); A("date", {"WFDateActionMode": "Current Date"}, u); return out(u, "Date")
def adjust(date_v, op, mag=None, unit=None):
    u = U(); p = {"WFDate": tok(date_v), "WFAdjustOperation": op}
    if mag is not None:
        p["WFDuration"] = {"Value": {"Magnitude": mag, "Unit": unit}, "WFSerializationType": "WFQuantityFieldValue"}
    A("adjustdate", p, u); return out(u, "Adjusted Date")
def fmt_date(date_v):
    u = U(); A("format.date", {"WFDateFormatStyle": "Custom", "WFDateFormat": FMT, "WFDate": tok(date_v)}, u); return out(u, "Formatted Date")
def details(inp, prop):
    u = U(); A("properties.health.quantity", {"WFInput": att(inp), "WFContentItemPropertyName": prop}, u); return out(u, prop)
def guarded(inp, op, vname, via_duration=False):
    """vname = '' then, only if the find returned samples, vname = stat(...)"""
    u = U(); A("gettext", {"WFTextActionText": tok("")}, u); setvar(vname, out(u, "Text"))
    g = U()
    A("conditional", {"WFControlFlowMode": 0, "GroupingIdentifier": g, "WFCondition": 100,
                      "WFInput": {"Type": "Variable", "Variable": att(inp)}})
    src = details(inp, "Duration") if via_duration else inp
    setvar(vname, stats(src, op))
    A("conditional", {"WFControlFlowMode": 2, "GroupingIdentifier": g}, U())
def stats(inp, op):
    u = U(); A("statistics", {"WFStatisticsOperation": op, "Input": att(inp)}, u); return out(u, "Statistics")
def enum_row(prop, value, op=4, removable=True):
    return {"Bounded": True, "Operator": op, "Property": prop, "Removable": removable,
            "Values": {"Enumeration": {"Value": value, "WFSerializationType": "WFStringSubstitutableState"}}}
def str_row(prop, value, op=4):
    return {"Bounded": True, "Operator": op, "Property": prop, "Removable": True, "Values": {"Unit": 4, "String": value}}
def between_row(prop, a, b):
    return {"Bounded": True, "Operator": 1003, "Property": prop, "Removable": True,
            "Values": {"Date": att(a), "AnotherDate": att(b), "Unit": 16, "Number": "1"}}
def find_health(htype, rows, group_by=None):
    u = U()
    p = {"WFContentItemFilter": {"Value": {"WFActionParameterFilterPrefix": 1,
            "WFActionParameterFilterTemplates": [enum_row("Type", htype, removable=False)] + rows,
            "WFContentPredicateBoundedDate": False}, "WFSerializationType": "WFContentPredicateTableTemplate"},
         "WFContentItemSortProperty": "Start Date", "WFContentItemSortOrder": "Oldest First",
         "WFContentItemLimitEnabled": False, "WFHKSampleFilteringFillMissing": False}
    if group_by: p["WFHKSampleFilteringGroupBy"] = group_by
    A("filter.health.quantity", p, u); return out(u, "Health Samples")

# ---------- build ----------
def build(repeat_count, show_result, name):
    global actions; actions = []
    g = U()
    setvar("Cursor", date_now())
    A("repeat.count", {"WFControlFlowMode": 0, "GroupingIdentifier": g, "WFRepeatCount": repeat_count})
    # --- dates: step the cursor back one day per iteration (plain magnitudes only)
    d1 = adjust(var("Cursor"), "Subtract", "1", "days"); setvar("Cursor", d1)
    d2 = adjust(var("Cursor"), "Get Start of Day"); setvar("DayStart", d2)
    d3 = adjust(var("DayStart"), "Add", "1", "days"); setvar("DayEnd", d3)
    d4 = adjust(var("DayStart"), "Add", "18", "hr"); setvar("SleepStart", d4)
    d5 = adjust(var("DayStart"), "Add", "36", "hr"); setvar("SleepEnd", d5)
    st = fmt_date(var("DayStart")); setvar("Stamp", st)
    day = lambda: [between_row("Start Date", var("DayStart"), var("DayEnd"))]
    night = lambda: [between_row("Start Date", var("SleepStart"), var("SleepEnd"))]
    # --- daily quantity metrics
    for htype, op, vname in [("Steps", "Sum", "Steps"), ("Active Calories", "Sum", "Energy"),
                             ("Resting Heart Rate", "Average", "RHR"), ("Heart Rate Variability", "Average", "HRV")]:
        hs = find_health(htype, day(), "Day"); guarded(hs, op, vname)
    # --- heart rate averages (works even without Apple Watch RHR/HRV)
    hs = find_health("Heart Rate", day()); guarded(hs, "Average", "HRDay")
    hs = find_health("Heart Rate", night()); guarded(hs, "Average", "HRNight")
    # --- sleep: total asleep = everything except In Bed / Awake; then stages
    for stage, vname in [("Deep", "SleepDeep"), ("REM", "SleepREM"), ("Core", "SleepCore"), ("Asleep", "SleepUnspec")]:
        hs = find_health("Sleep", night() + [str_row("Value", stage)]); guarded(hs, "Sum", vname, via_duration=True)
    # --- workouts
    wk = find_health("Workouts", day())
    g2 = U()
    A("repeat.each", {"WFControlFlowMode": 0, "GroupingIdentifier": g2, "WFInput": att(wk)})
    ws = fmt_date(var("Repeat Item", "Start Date")); we = fmt_date(var("Repeat Item", "End Date"))
    A("gettext", {"WFTextActionText": tokjson(
        '{"id":"wk-START","name":"TYPE","start":"START","end":"END","value":"VALUE","duration_text":"DUR","source":"Shortcuts"}',
        {"START": ws, "END": we, "TYPE": var("Repeat Item", "Name"), "VALUE": var("Repeat Item", "Value"), "DUR": var("Repeat Item", "Duration")})}, U())
    end2 = U(); A("repeat.each", {"WFControlFlowMode": 2, "GroupingIdentifier": g2}, end2)
    cu = U(); A("text.combine", {"text": att(out(end2, "Repeat Results")), "WFTextSeparator": "Custom", "WFTextCustomSeparator": ","}, cu)
    setvar("Workouts", out(cu, "Combined Text"))
    # --- body
    def m(name, units, v): return '{"name":"%s","units":"%s","data":[{"date":"STAMP","qty":"%s","source":"Shortcuts"}]}' % (name, units, v)
    body = '{"data":{"metrics":[' + ",".join([
        m("step_count", "count", "STEPS"), m("active_energy", "kcal", "ENERGY"),
        m("resting_heart_rate", "bpm", "RHR"), m("heart_rate_variability", "ms", "HRV"),
        m("heart_rate_day_avg", "bpm", "HR_DAY"), m("heart_rate_sleep_avg", "bpm", "HR_NIGHT"),
        m("sleep_deep", "s", "SLEEP_DEEP"),
        m("sleep_rem", "s", "SLEEP_REM"), m("sleep_core", "s", "SLEEP_CORE"), m("sleep_unspecified", "s", "SLEEP_UNSPEC")]) + '],"workouts":[WORKOUTS]}}'
    tu = U()
    A("gettext", {"WFTextActionText": tokjson(body, {
        "STAMP": var("Stamp"), "STEPS": var("Steps"), "ENERGY": var("Energy"), "RHR": var("RHR"), "HRV": var("HRV"), "HR_DAY": var("HRDay"), "HR_NIGHT": var("HRNight"),
        "SLEEP_DEEP": var("SleepDeep"), "SLEEP_REM": var("SleepREM"),
        "SLEEP_CORE": var("SleepCore"), "SLEEP_UNSPEC": var("SleepUnspec"), "WORKOUTS": var("Workouts")})}, tu)
    ru = U()
    A("downloadurl", {"WFURL": INGEST, "WFHTTPMethod": "POST", "ShowHeaders": True,
        "WFHTTPHeaders": {"Value": {"WFDictionaryFieldValueItems": [
            {"WFKey": tok("Authorization"), "WFItemType": 0, "WFValue": tok("Bearer " + SECRET)},
            {"WFKey": tok("Content-Type"), "WFItemType": 0, "WFValue": tok("application/json")}]},
            "WFSerializationType": "WFDictionaryFieldValue"},
        "WFHTTPBodyType": "File", "WFRequestVariable": att(out(tu, "Text"))}, ru)
    if show_result:
        A("showresult", {"Text": tok("v7 | steps=", var("Steps"), " | sleep(s) deep=", var("SleepDeep"),
            " rem=", var("SleepREM"), " core=", var("SleepCore"), " unspec=", var("SleepUnspec"), " | rhr=", var("RHR"), " hrDay=", var("HRDay"), " hrNight=", var("HRNight"),
            " | kcal=", var("Energy"), " | server: ", out(ru, "Contents of URL"))})
    A("repeat.count", {"WFControlFlowMode": 2, "GroupingIdentifier": g}, U())
    if not show_result:
        A("showresult", {"Text": tok("Backfill finished. ", out(ru, "Contents of URL"))})
    return {
        "WFWorkflowClientVersion": "2607.0.3", "WFWorkflowMinimumClientVersion": 900, "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59764},
        "WFWorkflowTypes": [], "WFWorkflowHasShortcutInputVariables": False, "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": ["WFAppStoreAppContentItem","WFArticleContentItem","WFContactContentItem","WFDateContentItem","WFEmailAddressContentItem","WFGenericFileContentItem","WFImageContentItem","WFiTunesProductContentItem","WFLocationContentItem","WFDCMapsLinkContentItem","WFAVAssetContentItem","WFPDFContentItem","WFPhoneNumberContentItem","WFRichTextContentItem","WFSafariWebPageContentItem","WFStringContentItem","WFURLContentItem"],
        "WFWorkflowActions": actions, "WFWorkflowName": name,
    }

def build_diag(name):
    global actions; actions = []
    now = date_now(); setvar("Now", now)
    ago = adjust(var("Now"), "Subtract", "7", "days"); setvar("WeekAgo", ago)
    prev = None
    for htype in ["Steps", "Active Calories", "Heart Rate", "Resting Heart Rate", "Heart Rate Variability", "Sleep", "Workouts", "Walking + Running Distance"]:
        hs = find_health(htype, [between_row("Start Date", var("WeekAgo"), var("Now"))])
        cu = U(); A("count", {"WFCountType": "Items", "Input": att(hs)}, cu)
        line = [htype + ": ", out(cu, "Count"), " samples in last 7 days"]
        tu = U(); A("gettext", {"WFTextActionText": tok(*(([prev, "\n"] if prev else []) + line))}, tu)
        prev = out(tu, "Text")
    A("showresult", {"Text": tok(prev)})
    diag = actions
    meta = build(1, True, name); meta["WFWorkflowActions"] = diag
    return meta

for count, show, name in [(1, True, "Health Sync v7"), (30, False, "Health Backfill v7")]:
    d = build_diag(name) if count is None else build(count, show, name)
    path = os.path.join(OUT, name + ".shortcut")
    with open(path, "wb") as f: plistlib.dump(d, f, fmt=plistlib.FMT_BINARY)
    print("wrote", path, "actions:", len(d["WFWorkflowActions"]))
