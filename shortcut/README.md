# Shortcut generator

`gen_shortcut.py` writes four iOS Shortcut files as binary plists. None of them
contains your secret: the three that talk to the server ask for it when they are
imported on the phone.

```bash
cp config.env.example config.env               # INGEST_URL only
python3 gen_shortcut.py config.env out/
python3 -m unittest discover -s tests          # 17 structural checks
shortcuts sign --mode anyone --input "out/Health Sync.shortcut" --output "Health Sync.shortcut"
```

| File | Purpose |
|---|---|
| **Health Sync** | Sends yesterday and the two days before it, silently. Automate this one at 08:30. The three-day window heals any morning the phone was locked. |
| **Health Check** | One day, and shows the values found plus the server's reply. Run after any change. |
| **Health Backfill** | 30 days. First setup, or after a long outage. |
| **Sleep Diagnostic** | Read-only, sends nothing. Reports what sleep data Health holds and which stage labels match. |

## What a sync run sends

For each day in the window, one JSON body in the Health Auto Export shape, all
numbers as strings:

| Metric stored | Health type | How |
|---|---|---|
| `step_count` | Steps | grouped by Day, Sum |
| `active_energy` | Active Calories | grouped by Day, Sum |
| `resting_heart_rate` | Resting Heart Rate | grouped by Day, Average |
| `heart_rate_variability` | Heart Rate Variability | grouped by Day, Average |
| `heart_rate_day_avg` | Heart Rate | samples within the calendar day, Average |
| `heart_rate_sleep_avg` | Heart Rate | samples 18:00 → 12:00 next day, Average |
| `sleep_deep` / `sleep_rem` / `sleep_core` / `sleep_unspecified` | Sleep, filtered by stage | Get Details → Duration, Sum (seconds) |
| workouts | Workouts | one JSON object each |
| `sleep_samples_n` / `heart_rate_samples_n` | Sleep, Heart Rate | how many samples Health returned for that window |

A metric with no samples is sent as an empty string and stored as null, which is
how the briefing can tell "did not sync" from "zero".

The two `_samples_n` counts make a null self-explaining. A null value with a
count of 0 means Health returned nothing at all: the watch was not syncing, or
the phone was locked when the automation fired, since Health is unreadable then.
A null value with a count above 0 means the samples exist but the filter did not
match them, which is a bug in the generator.

The serialization details, the Health type names, and every trap found while
building this are in [CLAUDE.md](CLAUDE.md).
