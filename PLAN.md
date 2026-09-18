# PLAN

Living status. Update it in the same commit as the work it describes.

## Phases

| # | Phase | Status | Commit |
|---|---|---|---|
| 1 | Remote MCP server on Vercel + Neon, OAuth, ingest patches for Shortcuts payloads | Done | `75f7062` |
| 2 | iOS Shortcut ingest: generator, signing, Health type names and sleep durations | Done | `75f7062` |
| 3 | Telegram bot and daily Claude routine (09:00 IST), analytical prompt on Opus | Done | `75f7062` |
| 4 | Public repo, README, troubleshooting | Done | `75f7062` |
| 5 | Resilience: self-healing 3-day sync, secret asked at import, sleep diagnostic, partial-sync reporting, generator tests, project docs | Done | `188ecbc` |
| 6 | Confirm on device why sleep stopped matching, then pin the correct labels | In progress | — |

## In progress

**Phase 6 — sleep stopped syncing after 15 Sep 2026.** Rows for 16 and 17 Sep
arrived with steps and active energy but every sleep stage null, so the phone
posted and the `Sleep` + stage-label filters matched nothing. Two candidate
causes: Health holds no sleep for those nights (watch not worn or not synced),
or an iOS update renamed the sleep stage labels. `Sleep Diagnostic` answers this
on the device: it reports sample counts for `Sleep` and `Sleep Analysis`, counts
per stage label, and the raw values Health returns for last night. Pin the
labels in `SLEEP_STAGES` once the answer is known.

## Left to do

- Pin sleep labels from the diagnostic result (phase 6).
- Screenshot of a real briefing in the README.
- Consider a `created_at` column on `metric_samples` so a late sync can be told
  apart from an on-time one.

## Principles

See [CLAUDE.md](CLAUDE.md). The short version: never invent a number, never
commit a secret, never rename a stored metric, and verify Shortcuts
serialization against real exported files.
