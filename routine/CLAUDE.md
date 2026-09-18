# routine/ — the scheduled Claude agent

[prompt.md](prompt.md) is the source of truth for what the briefing says.
[README.md](README.md) covers creating and debugging the routine.

## Shape

A cloud agent, cron `30 3 * * *` (09:00 Asia/Kolkata), model `claude-opus-5`,
the `health` connector, Bash for curl. It queries 60 days, does the arithmetic
in a scratch script rather than by eye, then posts to Telegram.

## Gotchas

- **Cron is UTC.** 09:00 IST is `30 3 * * *`.
- **Schedule it after the phone sync**, not before. The sync runs 08:30; the
  routine 09:00.
- **Telegram credentials live in the prompt.** The routine API did not expose
  environment variables at the time of writing, so anyone who can open the
  routine or its run logs can read the bot token. Rotate it there if it leaks.
- **Partial rows are the normal failure mode**, not empty ones. The prompt has a
  PARTIAL SYNC section: report the gap, never treat a null as a zero.
- **Debug with the API, not the web UI**: `list_runs` then `get_run_log`. A
  healthy run ends with `"ok":true` and a message id, and takes about 3 minutes
  on Opus. A 40-second run means it bailed to the missing-data path.
