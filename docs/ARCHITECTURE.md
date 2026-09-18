# Architecture

```
iPhone (Apple Health, Pebble watch writes into it)
   │  iOS Shortcut, daily: yesterday and the two days before it
   │  POST JSON + Bearer secret
   ▼
/api/ingest ── Next.js on Vercel ──▶ Neon Postgres (metric_samples, workouts, health_events)
                    │
                    ├── /api/mcp          remote MCP server, OAuth 2.1
                    └── /.well-known/...  discovery for claude.ai
                                 ▲
                                 │ custom connector "health"
                    Claude routine, 03:30 UTC = 09:00 IST
                                 │ analyses 60 days, writes the briefing
                                 ▼
                          api.telegram.org → your chat
```

## Why it is shaped this way

**Why a remote MCP server rather than a local one.** Scheduled Claude routines
run in Anthropic's cloud and can only reach claude.ai connectors. A local MCP
server on the Mac is unreachable from there, and the Mac is not always on. The
server therefore has to be an HTTPS endpoint with its own auth.

**Why the iPhone pushes instead of the server pulling.** HealthKit has no cloud
API. Only the phone can read it, so the phone must initiate. That makes the
phone the weakest link in the chain, which is why the sync sends three days per
run: any single missed morning heals itself the next day, because the server
upserts on (metric, timestamp, source).

**Why daily totals rather than raw samples.** The briefing needs one number per
metric per day. Aggregating on the phone keeps the payload small, the SQL
trivial, and the row count in the free Neon tier negligible.

**Why the secret is asked for at import.** Embedding it produced files that
could not be shared, stored, or committed, and it was the only reason the
repository needed a secret-scanning step before every push. An import question
keeps the secret on the device that uses it.

**Why nulls are stored rather than skipped.** A null row records that the phone
reported and Health had nothing. That distinction is what lets the briefing say
"sleep did not sync" instead of "you slept zero hours", and it is what turned a
silent two-day outage into a diagnosable one.

**Why the analysis happens in the routine, not in SQL.** The interesting output
is interpretation: sleep architecture, load versus recovery, multi-day drift.
That is a language-model task. SQL just returns one clean row per day.
