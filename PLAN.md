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
| 6 | Confirm on device why sleep stopped matching, then pin the correct labels | Resolved by itself | — |
| 7 | Workouts: guard the loop, drop blank rows, derive duration, put gym sessions in the briefing | Done | `54643e0` |
| 6a | Record sample counts with every sync so a null value is self-explaining | Done | `32af353` |

## In progress

**Phase 7 — workouts, handed over from the Milo session.** Milo (the user's gym
log) now writes each finished session to Apple Health with a start and an end and
nothing else, and those sessions should appear in the briefing. The workouts path
had never worked: the table held exactly one row, `wk-` with every field blank.

Fixed and shipped:

- The Shortcuts workouts loop is guarded, so an empty list emits nothing. The
  blank row came from a repeat over an empty list emitting one all-empty object.
- `normalize()` drops any workout with no parseable start and counts it as
  skipped, so a blank object can never be stored again.
- Duration is derived from start and end unless the payload carries a bare
  number. Shortcuts renders a duration as a localized measurement ("45 min"),
  which the lenient `num()` would have read as 45 seconds.
- The sync sends only id, name, start and end. Energy, distance and heart rate
  are omitted rather than zeroed, because Milo records none of them.
- The stray `wk-` row was deleted from production.
- The briefing has a WORKOUTS section: sessions listed with name, start time and
  minutes; weekly count and total minutes in Trends; no inference of effort or
  calories; silence when there are no workouts rather than nagging.

**Still unverified: no real workout has ever reached the server.** The workout
property names beyond Start Date, End Date and Name are unproven, which is what
`Workouts Diagnostic` exists to settle. Do not claim workouts export until a row
with a real start, end and duration has been seen on the server.

**Phase 6 closed itself.** Sleep and heart rate returned on 23 and 24 Sep without
any change to the filters, which fits the watch or a locked phone rather than
renamed labels. The `_samples_n` counts added in 6a will name the cause if it
recurs. Note the sync is still running only about 5 days in 14, and the counts
have never arrived, so the newest shortcuts have not been imported yet.

## Left to do

- Pin sleep labels from the diagnostic result (phase 6).
- Screenshot of a real briefing in the README.
- Consider a `created_at` column on `metric_samples` so a late sync can be told
  apart from an on-time one.
- Pin the workout property names once Workouts Diagnostic reports them, and add
  any that Milo fills (it currently fills none beyond name and the timestamps).

## Principles

See [CLAUDE.md](CLAUDE.md). The short version: never invent a number, never
commit a secret, never rename a stored metric, and verify Shortcuts
serialization against real exported files.
