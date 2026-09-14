# Shortcut generator

`gen_shortcut.py` writes two iOS Shortcut files as binary plists:

- **Health Sync** sends yesterday's data (one day per run). Automate it daily.
- **Health Backfill** is the same body looped over the last 30 days. Run once.

Both read the config file for `MCP_SECRET` and `INGEST_URL`, so the generated files contain your secret. Never commit them; the repo `.gitignore` excludes `*.shortcut`.

## What each run does

For the target day (a cursor that steps back one day per loop iteration):

| Metric sent | Health type | How |
|---|---|---|
| `step_count` | Steps | Find Health Samples, grouped by Day, Sum |
| `active_energy` | Active Calories | grouped by Day, Sum |
| `resting_heart_rate` | Resting Heart Rate | grouped by Day, Average (empty on devices that don't write it) |
| `heart_rate_variability` | Heart Rate Variability | grouped by Day, Average (empty on Pebble) |
| `heart_rate_day_avg` | Heart Rate | samples in the calendar day, Average |
| `heart_rate_sleep_avg` | Heart Rate | samples 18:00 → 12:00 next day, Average |
| `sleep_deep` / `sleep_rem` / `sleep_core` / `sleep_unspecified` | Sleep, filtered by Value | Get Details → Duration, Sum (seconds) |
| workouts | Workouts | one JSON object per workout |

Every calculation is wrapped in an "If Health Samples has any value" guard so a day with no data does not abort the run. The JSON body follows the Health Auto Export shape the server expects, with all numbers as strings.

## Signing

iOS refuses unsigned shortcut files. On a Mac:

```bash
shortcuts sign --mode anyone --input "Health Sync v7.shortcut" --output "Health Sync.shortcut"
```

## Lessons from reverse-engineering the format

Getting these right cost several iterations; they are baked into the generator so you don't repeat them.

- Health types are addressed by display name in a `Type` filter row: `Steps`, `Active Calories` (not "Active Energy"), `Sleep` (not "Sleep Analysis"), `Heart Rate`, `Resting Heart Rate`, `Heart Rate Variability`, `Workouts`. A wrong name silently returns nothing and iOS never asks for that permission.
- Sleep stage filters use the string form `{"Values": {"Unit": 4, "String": "Deep"}}` with values `Asleep`, `Core`, `Deep`, `REM`, `In Bed`, `Awake`.
- Sleep samples carry a text value, so summing the samples fails; sum the `Duration` property instead. Durations come back in seconds.
- Date ranges use operator `1003` ("is between") with `Date` and `AnotherDate` attachments. Variable magnitudes inside Adjust Date did not resolve, hence the plain-number cursor loop.
- The health-specific parameter keys are `WFHKSampleFilteringGroupBy`, `WFHKSampleFilteringFillMissing` and `WFHKSampleFilteringUnit`; they are not in the macOS action catalogue but are in its localisation table.
- Real examples were pulled from iCloud shortcut links via `https://www.icloud.com/shortcuts/api/records/<id>`, which returns a download URL for the raw plist.
