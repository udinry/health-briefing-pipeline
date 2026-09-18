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
| 6a | Record sample counts with every sync so a null value is self-explaining | Done | `a5e770c` |

## In progress

**Phase 6 — sleep stopped syncing after 13 Sep 2026.** A full audit of the
server on 18 Sep (every metric name, both other tables, the `extra` column)
found nothing stored under an unexpected label: ten metric names, one source,
no events. The gap is upstream of the server.

What the per-day table shows:

| Day | steps | kcal | heart rate | sleep |
|---|---|---|---|---|
| 09-13 and earlier | yes | yes | yes | yes |
| 09-14, 09-15 | no row at all | | | |
| 09-16 | yes | yes | yes | none |
| 09-17 | yes | yes | none | none |

Steps and active energy come from the iPhone itself; heart rate and sleep come
from the Pebble watch. Heart rate is matched with no label filter at all, so a
renamed sleep label cannot explain heart rate disappearing on 09-17. The
evidence points at the watch not writing to Apple Health rather than at the
shortcut's filters. `Sleep Diagnostic` distinguishes the two on the device: if
it reports zero `Sleep` samples over 14 days, the data is not in Health; if it
reports samples but zero matches per stage label, the labels changed and need
pinning in `SLEEP_STAGES`.

The user reports that Apple Health does hold values for the days in question,
which points away from the watch and towards the query returning nothing at run
time (a locked phone being the likeliest reason, since Health is unreadable
then). Every sync now posts `sleep_samples_n` and `heart_rate_samples_n`, so
from the next run the server itself records which case applies and no further
round trip through the phone is needed.

Also latent: `sleep_unspecified` has never had a value in 22 days, so the
`Asleep` label has never matched anything. Harmless while the three staged
labels work, but it should be confirmed by the same diagnostic.

## Left to do

- Pin sleep labels from the diagnostic result (phase 6).
- Screenshot of a real briefing in the README.
- Consider a `created_at` column on `metric_samples` so a late sync can be told
  apart from an on-time one.
- One empty workout row (`id` of `wk-`, every field blank) was stored on an early
  run: the per-workout loop emitted one all-empty object. Skip workouts with no
  parseable start in `normalize()`, add a test, and delete the stray row.

## Principles

See [CLAUDE.md](CLAUDE.md). The short version: never invent a number, never
commit a secret, never rename a stored metric, and verify Shortcuts
serialization against real exported files.
