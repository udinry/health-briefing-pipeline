# The scheduled routine

A Claude Code routine is a cloud agent that runs on a cron schedule with your claude.ai connectors attached. This one needs only the `health` connector and Bash (for curl).

## Create it

Either run `/schedule` in Claude Code and paste the prompt, or use the routines page at https://claude.ai/code/routines. The configuration used here:

| Setting | Value |
|---|---|
| Name | Daily health summary → Telegram |
| Schedule | `30 3 * * *` (09:00 Asia/Kolkata; cron is UTC) |
| Model | claude-opus-5 (claude-sonnet-5 also works, faster and cheaper, shallower analysis) |
| Connectors | `health` only |
| Allowed tools | Bash, Read, Write, Glob, Grep |
| Prompt | [prompt.md](prompt.md) with placeholders filled |

Schedule the routine about 30 minutes after the iPhone Shortcut automation so yesterday's data is on the server.

## Credentials

The routine environment did not expose environment variables through the API at the time of writing, so the Telegram token is pasted into the prompt. Anyone who can open the routine or its run logs can read it. If your environment supports env vars, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` there and reference them in the curl command instead.

## Check a run

Each run's log shows the SQL it ran, the arithmetic it did, and the Telegram API response. A healthy run ends with `"ok":true` and a message id. The first run takes about 3 minutes on Opus.
