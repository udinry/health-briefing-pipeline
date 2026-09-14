# Changes from upstream

Upstream: https://github.com/mikipalet/apple-health-mcp (MIT).

Two small patches in `lib/ingest.ts`, with tests in `tests/ingest.test.ts`:

1. **Numeric strings are accepted for `qty`.** iOS Shortcuts renders numbers into text using the device locale, so values arrive as `"7359"`, `"1,234"` or `"58,4"`. The normaliser now parses those, handling thousands separators and comma decimals.
2. **Measurement strings are accepted.** Shortcuts renders workout energy as `"245 kcal"` and HRV as `"58.4 ms"`. The leading numeric token is used.

Everything else (schema, tools, OAuth layer, deployment) is unchanged, so upstream instructions still apply.
