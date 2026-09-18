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
- `MCP_SECRET` is both the ingest bearer token and the OAuth login. Treat it
  like a password.
