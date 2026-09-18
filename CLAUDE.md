# Agent entry point

Read [PLAN.md](PLAN.md) first: it is the living status of this project. Then
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for why the pieces are shaped the
way they are. Each directory has its own `CLAUDE.md` with the gotchas that cost
real debugging time — read the one for the directory you are about to touch.

## What this is

A daily health briefing pipeline: an iOS Shortcut pushes Apple Health daily
totals to a remote MCP server on Vercel; a scheduled Claude routine reads that
server through a claude.ai connector, analyses the history, and sends a
briefing to Telegram.

## Non-negotiables

- **Never invent a number.** Every figure in a briefing traces to a stored row.
  A missing metric is reported as missing, never as zero. This is why the
  server stores nulls rather than dropping empty values.
- **No secrets in the repo, and none in a generated shortcut file.** The
  shortcut asks for the MCP secret when it is imported on the phone. `*.shortcut`
  and `*.env` (except `.example`) are gitignored. Verify before every push:
  `git grep -nI -E '[0-9a-f]{40,}|[0-9]{9,10}:AA'`.
- **Stored metric names never change.** Renaming one silently splits its
  history in the database. `shortcut/tests` enforces this.
- **Verify Shortcuts serialization against a real exported shortcut**, not from
  memory. Wrong strings fail silently: the action matches nothing, iOS never
  asks for the permission, and the row arrives null.

## Source control

Commit and push straight to `main`. No feature branches, no PRs, never
force-push. Docs land in the same commit as the code they describe. Attribution
lines go at the end of commit messages.

## Tests

```bash
python3 -m unittest discover -s shortcut/tests   # generator structure, 17 tests
cd server && npm ci && npm test                  # ingest + OAuth, 53 tests
```
