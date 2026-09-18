# Troubleshooting

**Rows arrive but one metric is always null (e.g. sleep).**
The phone posted and Health returned nothing for that metric. Either the data is
not in Health for those days, or the label the filter matches on has changed.
Run **Sleep Diagnostic** on the phone: it reports sample counts for the `Sleep`
and `Sleep Analysis` type names, counts for each stage label, and the raw values
Health returns for last night. Pin whatever it reports in `SLEEP_STAGES` in
`shortcut/gen_shortcut.py`, regenerate and re-sign.

**A whole day is missing, no row at all.**
The shortcut did not run, or it failed before the POST. The usual cause is the
phone being locked when the automation fired: Apple Health is unreadable while
locked. Health Sync sends three days per run so the next run fills the gap; open
it manually to catch up immediately.

**The briefing says "sync appears broken".**
That is the routine doing its job. Check the last synced date it names, run
Health Sync on the phone, and confirm the 08:30 automation still exists under
the Automation tab.

**A wrong secret after import.**
Run Health Check. It prints the server's reply: `{"error":"unauthorized"}` means
the pasted secret is wrong or picked up stray whitespace. Re-import and paste
again.

**The Shortcut result box shows `metricsStored` but values are empty.**
Health returns nothing, without an error, for any type Shortcuts is not allowed to read. Check Settings → Privacy & Security → Health → Shortcuts. If a type is missing from that list entirely, the Shortcut never asked for it, which means its type name did not match; see the type names in `shortcut/README.md`.

**"Calculate Statistics failed because Shortcuts couldn't convert from Text to Number."**
A category sample (sleep) was summed directly. The generator sums `Duration` instead. Regenerate.

**Sleep hours look 3,600× too big.**
Durations are seconds. The server stores them as-is with units `s`; the prompt divides by 3,600.

**The backfill stops after one day.**
A day with no samples aborted a calculation. Every statistic is now wrapped in an
"has any value" guard, and `shortcut/tests` fails if one is not.

**Re-importing a shortcut keeps the old one.**
iOS adds a second copy with the same name. Delete the old one first, or rename versions.

**Looking up a Shortcuts action's parameters on macOS 26.**
`WorkflowKit.framework/Resources/WFActions.plist` no longer exists. Use a real
exported shortcut instead: `https://www.icloud.com/shortcuts/api/records/<id>`
returns a download URL for the raw plist.

**Steps are stamped for today instead of yesterday.**
The day offset must be a plain number inside Adjust Date; a variable there silently became zero. The generator uses a cursor that steps back one day per loop.

**claude.ai connector shows no tools.**
Confirm `/.well-known/oauth-authorization-server` returns JSON at your Vercel URL and that you chose "Sign in now" plus "Register automatically" when adding the connector.

**Routine sends "sync appears broken".**
The Shortcut automation did not run, or ran after the routine. Make sure it is set to Run Immediately and scheduled before the routine.
