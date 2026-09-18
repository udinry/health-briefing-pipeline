# shortcut/ — the iOS Shortcut generator

`gen_shortcut.py` writes binary-plist `.shortcut` files. `shortcuts sign` on
macOS makes them importable on iOS. Nothing here needs the secret: each file
asks for it at import time.

```bash
python3 gen_shortcut.py config.env out/        # config.env holds INGEST_URL only
shortcuts sign --mode anyone --input "out/Health Sync.shortcut" --output "Health Sync.shortcut"
python3 -m unittest discover -s tests          # 17 structural tests
```

| File produced | Purpose |
|---|---|
| Health Sync | 3 days per run, silent. The one to automate. |
| Health Check | 1 day, shows values found and the server's reply. Use after any change. |
| Health Backfill | 30 days. First setup, or after a long outage. |
| Sleep Diagnostic | Read-only. Reports what sleep data Health actually holds. |

## Gotchas, all of them found the hard way

- **A wrong Health type name fails silently.** The action matches nothing, iOS
  never asks for that permission, and the row arrives null. Correct names:
  `Steps`, `Active Calories` (not "Active Energy"), `Sleep` (not "Sleep
  Analysis"), `Heart Rate`, `Resting Heart Rate`, `Heart Rate Variability`,
  `Workouts`. If a permission is missing from Settings → Privacy & Security →
  Health → Shortcuts, the name is wrong.
- **Sleep stage values are plain strings, not enumerations**:
  `{"Values": {"Unit": 4, "String": "Deep"}}`. Labels: Asleep, Core, Deep, REM,
  In Bed, Awake. These have moved between OS releases — that is what Sleep
  Diagnostic is for.
- **Sleep samples carry a text value**, so summing the samples throws "couldn't
  convert from Text to Number". Sum the `Duration` property instead; it comes
  back in seconds.
- **Every statistic needs an "has any value" guard.** One metric with no samples
  aborts the entire run, which is how a 30-day backfill once died on day two.
- **Adjust Date magnitudes must be literal numbers.** A variable there silently
  resolves to zero, which once stamped every sample with today's date. Hence the
  cursor loop.
- **Date filters use operator 1003** ("is between") with `Date` and
  `AnotherDate` attachments and `Unit: 16`.
- **Health is unreadable while the phone is locked** (`RequiresUnlock` on the
  find action), so a time-of-day automation only works if the phone is unlocked
  at that moment. This is the most likely cause of a morning with no row at all.
- **Re-importing a shortcut with the same name keeps the old one too.** Delete
  the old one first or iOS will keep running it.
- **The action catalogue moved.** On macOS 13 it was
  `WorkflowKit.framework/Resources/WFActions.plist`; on macOS 26 that file is
  gone. Real exported shortcuts are the reliable reference: fetch one with
  `https://www.icloud.com/shortcuts/api/records/<id>`, which returns a download
  URL for the raw plist.
