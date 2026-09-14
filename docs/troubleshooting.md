# Troubleshooting

**The Shortcut result box shows `metricsStored` but values are empty.**
Health returns nothing, without an error, for any type Shortcuts is not allowed to read. Check Settings → Privacy & Security → Health → Shortcuts. If a type is missing from that list entirely, the Shortcut never asked for it, which means its type name did not match; see the type names in `shortcut/README.md`.

**"Calculate Statistics failed because Shortcuts couldn't convert from Text to Number."**
A category sample (sleep) was summed directly. The generator sums `Duration` instead. Regenerate.

**Sleep hours look 3,600× too big.**
Durations are seconds. The server stores them as-is with units `s`; the prompt divides by 3,600.

**The backfill stops after one day.**
A day with no samples aborted a calculation. Versions from v7 on guard every statistic with an "has any value" check.

**Re-importing a shortcut keeps the old one.**
iOS adds a second copy with the same name. Delete the old one first, or rename versions.

**Steps are stamped for today instead of yesterday.**
The day offset must be a plain number inside Adjust Date; a variable there silently became zero. The generator uses a cursor that steps back one day per loop.

**claude.ai connector shows no tools.**
Confirm `/.well-known/oauth-authorization-server` returns JSON at your Vercel URL and that you chose "Sign in now" plus "Register automatically" when adding the connector.

**Routine sends "sync appears broken".**
The Shortcut automation did not run, or ran after the routine. Make sure it is set to Run Immediately and scheduled before the routine.
