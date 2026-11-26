# Analyze performance

Resolve the advertiser and reporting timezone with `account`. Use the requested date range, or the last seven **completed** calendar days in that timezone when the user gives none. Pass the inclusive dates explicitly to `report`. For campaign selection with performance, join `read list-campaigns` to campaign-level Insights by campaign ID.

```bash
bash <skill-path>/scripts/chatgpt_ads.sh report --since 2026-09-01 --until 2026-09-07 --output ./campaigns.json
bash <skill-path>/scripts/chatgpt_ads.sh report --scope campaign --id CAMPAIGN_ID --level ad --granularity none --since 2026-09-01 --until 2026-09-07
```

Dates are inclusive and use the account timezone. By default the report returns daily campaign rows across the account. Select an account, campaign, ad group or ad scope and an equal or lower aggregation level. Use `hourly`, `daily`, `monthly`, or `none` for period totals. Default metrics are impressions, clicks, spend, CTR, CPC and CPM. Use `--options` to request supported conversion, sales and ROAS fields, attribution windows, segments, filters and sorting. The helper follows every page and preserves native row values. Summarize the date range, account currency and attribution basis; an empty result means the API returned no rows.

For event-specific results use `read post-conversion-insights --body ./report.json` with the [documented attribution window and fields](advertiser-operations.md#pixel-events-attribution-and-diagnosis). Keep missing values distinct from reported zeros. Route questions about missing delivery or tracking to [Diagnose](diagnose.md). Present any proposed campaign change separately through [Manage](manage.md).
