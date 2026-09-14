# Daily AI health briefing: Apple Health → MCP → Claude routine → Telegram

Every morning a Claude routine reads your Apple Health history, analyses it like a coach, and sends a short briefing to Telegram: what yesterday's numbers mean, week-over-week trends, and a concrete plan for the day.

It runs entirely on free tiers (Vercel, Neon Postgres, iOS Shortcuts, Telegram) plus a paid claude.ai plan for the custom connector and scheduled routine. No Apple Watch required: it was built and tested with a Pebble Core 2, and works with any wearable that writes to Apple Health.

```
Apple Health on iPhone
   └─ iOS Shortcut (08:30 daily) POSTs yesterday's totals ──▶ /api/ingest
                                                                │
                                              Neon Postgres ◀───┘
                                                                │
                              /api/mcp (remote MCP server, OAuth) ──▶ claude.ai custom connector
                                                                │
                                   Claude Code routine (09:00 daily) ── analyses ──▶ Telegram bot
```

## What the briefing looks like

> **Mixed — Sun 13 Sep:** your best night of sleep in a week, but a third straight day under 10k steps. 😴
>
> **Yesterday** — Steps 8,300 ↓ (7-day avg 11,000) · Active 74 kcal ↓ · Avg HR 73 bpm ↓ · Sleep 8h22m ↑ (deep 3.0h/36%, REM 1.8h/22%)
>
> **What it means** — HR has drifted down five days in a row (83→73) alongside a drop in steps: you are well recovered, not overtrained. In your own data, days above 13k steps are followed by ~9.1h sleep; days under 8k by ~6.7h …
>
> **Trends** — Weekly steps 75,900, down 10% on last week; rolling average turning down. Sleep tracked 7/7 nights vs 4/7 …
>
> **Plan for today** — 1) 11,500 steps brings the weekly average back above 10k … 2) Lights out by 23:45 … 3) …
>
> **Watch** — active energy: 74 kcal on 8,300 steps is far below your usual ratio, so Sunday's figure is probably incomplete.

## Repository layout

| Path | What it is |
|---|---|
| `server/` | The remote MCP server, a lightly patched copy of [mikipalet/apple-health-mcp](https://github.com/mikipalet/apple-health-mcp) (MIT). Next.js on Vercel, Neon Postgres, stateless OAuth 2.1 so claude.ai can connect. See [server/CHANGES.md](server/CHANGES.md) for the two patches. |
| `shortcut/` | `gen_shortcut.py` builds signed iOS Shortcut files that read Apple Health and POST to the server. No Health Auto Export subscription needed. |
| `routine/` | The routine prompt template and how to create the scheduled Claude Code routine. |
| `docs/` | Troubleshooting notes learned the hard way. |

## Setup

### 1. Deploy the server (about 15 minutes)

```bash
cd server
npm install
npm test                      # 53 tests, in-memory Postgres, no DB needed
npx vercel link               # creates the Vercel project
openssl rand -hex 32          # this is your MCP_SECRET; save it in a password manager
npx vercel env add MCP_SECRET production   # paste the secret (repeat for preview/development)
npx vercel integration add neon --name apple-health-db   # provisions Neon and sets DATABASE_URL
npx vercel deploy --prod
npx vercel env pull .env.production --environment production
DATABASE_URL="$(grep ^DATABASE_URL .env.production | cut -d'"' -f2)" npm run db:migrate
rm .env.production
```

Verify: `GET https://<app>.vercel.app/api/mcp` returns 401 with a `WWW-Authenticate` header, and `/.well-known/oauth-authorization-server` returns JSON.

The upstream README covers the same steps through the Vercel dashboard if you prefer clicking.

### 2. Push data from the iPhone (free, via Shortcuts)

The upstream project expects the Health Auto Export app, whose REST automation is a paid feature. This repo replaces it with a generated iOS Shortcut.

```bash
cd shortcut
cp config.env.example config.env      # fill in MCP_SECRET and INGEST_URL
python3 gen_shortcut.py config.env out/
cd out
shortcuts sign --mode anyone --input "Health Sync v7.shortcut"     --output "Health Sync.shortcut"
shortcuts sign --mode anyone --input "Health Backfill v7.shortcut" --output "Health Backfill.shortcut"
```

`shortcuts sign` is a built-in macOS command (macOS 12+). Unsigned shortcut files cannot be imported on iOS.

Send the two signed files to your iPhone (AirDrop or iCloud Drive), open each in the Files app and tap **Add Shortcut**. Then:

1. Run **Health Sync** once. Allow every Health permission prompt. A result box shows the values found and the server response.
2. Run **Health Backfill** once to load the last 30 days so weekly comparisons work immediately.
3. Shortcuts → **Automation** tab → **+** → **Time of Day** → 08:30, Daily, **Run Immediately**, Notify off → choose Health Sync.

Each run sends one day: steps, active calories, average heart rate (day and overnight), sleep stages (core/deep/REM/unspecified, in seconds), resting heart rate and HRV if your device records them, and workouts. Re-running a day is safe; the server upserts by metric and date.

See [shortcut/README.md](shortcut/README.md) for what the generator does and how it was reverse-engineered.

### 3. Telegram bot (2 minutes)

1. Message **@BotFather** → `/newbot` → pick a name and a username ending in `bot`. Save the token.
2. Send your new bot one message (`hi`).
3. Get your chat ID:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][-1]['message']['chat']['id'])"
   ```

### 4. Connect the server to claude.ai

claude.ai → Settings → Connectors → **Add custom connector**. Name it `health`, URL `https://<app>.vercel.app/api/mcp`, Authentication **Sign in now**, OAuth client **Register automatically**. Click **Connect** and enter your MCP_SECRET on the authorize page. The connector then lists six tools: `list_metrics`, `query_metric`, `list_workouts`, `query_events`, `latest_snapshot`, `health_sql`.

Custom connectors need a paid claude.ai plan.

### 5. Create the daily routine

Open Claude Code and run `/schedule`, or use claude.ai/code/routines. Use [routine/prompt.md](routine/prompt.md) as the prompt, replacing the placeholders. Schedule it for about 30 minutes after the Shortcut automation, in UTC (09:00 IST = `30 3 * * *`). Attach the `health` connector. Opus 5 gives noticeably better analysis than Sonnet; both work.

Trigger a manual run and check Telegram. Full details and a copy of the exact configuration are in [routine/README.md](routine/README.md).

## Why this design

- **Remote MCP, not local:** claude.ai routines run in the cloud and can only use claude.ai connectors, so the health data has to live behind an HTTPS MCP endpoint.
- **Shortcuts, not an export app:** the iPhone is the only thing that can read HealthKit. A Shortcut is free, runs on a schedule, and the generator makes it reproducible.
- **Daily totals, not raw samples:** the briefing needs one number per metric per day. Sending daily aggregates keeps the payload tiny and the SQL simple.
- **Credentials:** the MCP secret is both the ingest bearer token and the OAuth login. Treat it like a password.

## Known limitations

- iOS Shortcuts time-of-day automations run once a day, so the data is a daily snapshot, not hourly.
- HRV and resting heart rate appear only if your wearable writes them to Apple Health. Pebble does not write HRV.
- The day and night heart-rate averages came out identical on the test device; the prompt treats them as one figure.
- The claude.ai connector's OAuth token lasts 90 days; reconnect with the secret when the routine starts failing.

## Credits

The server is [apple-health-mcp](https://github.com/mikipalet/apple-health-mcp) by mikipalet, MIT licensed. The Shortcut serialization format was worked out from real exported shortcuts and the WorkflowKit action catalogue; see `shortcut/README.md`. Built with Claude Code.

## License

MIT. See [LICENSE](LICENSE). The `server/` directory keeps its original MIT license from upstream.
