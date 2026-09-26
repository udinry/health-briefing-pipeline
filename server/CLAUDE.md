# server/ — the remote MCP server

A copy of [mikipalet/apple-health-mcp](https://github.com/mikipalet/apple-health-mcp)
(MIT) with two patches; see [CHANGES.md](CHANGES.md). Next.js on Vercel, Neon
Postgres via Drizzle, a stateless OAuth 2.1 layer so claude.ai can connect.

## Layout

| Path | What |
|---|---|
| `app/api/ingest/` | POST endpoint the phone talks to. Auth, validate, normalise, persist. |
| `app/api/[transport]/` | The MCP endpoint itself. |
| `app/api/oauth/` | authorize / token / register / metadata. The authorize page is gated by `MCP_SECRET`. |
| `lib/ingest.ts` | Payload → rows. The patched `num()` lives here. |
| `lib/tools/` | One file per MCP tool. |
| `db/schema.ts` | `metric_samples`, `workouts`, `health_events`. |

## Testing

`npm test` — Vitest against in-memory PGlite, no database needed. 53 tests.

## Gotchas

- **`num()` must stay permissive.** iOS Shortcuts renders numbers as text using
  the device locale, so values arrive as `"7359"`, `"1,234"`, `"58,4"` or
  `"245 kcal"`. Tightening this silently nulls every metric.
- **Empty string means missing, not zero.** The shortcut sends `""` when Health
  returns no samples. `num()` maps that to null on purpose; the briefing depends
  on being able to tell the two apart.
- **Idempotency comes from the unique index** on (metric_name, date, source).
  That is what makes re-sending the same day safe, and the 3-day sync window
  possible.
- **A workout with no parseable start is dropped**, and counted in `skipped`. A
  Shortcuts repeat over an empty list once emitted a single all-empty object,
  which was stored as a blank workout row that read like a real session.
- **Workout duration is derived from the timestamps** unless the payload carries
  a bare number. Shortcuts renders a duration as a localized measurement
  ("45 min"), and the lenient `num()` would read that as 45 seconds.
- **Energy, distance and heart rate stay absent** when Health has none. The gym
  app records duration only, so a zero there would be invented data.
- `MCP_SECRET` is both the ingest bearer token and the OAuth login. Treat it
  like a password.
- **Tests set a 60s timeout** in `vitest.config.ts`. PGlite boots a Postgres wasm
  build per suite, and the 5s default fails under load in a way that reads like a
  broken test.
- **Deploying:** `server/.vercel` (gitignored) links this directory to the
  existing Vercel project, so `npx vercel deploy --prod` from here updates
  production rather than creating a second project.
