# CTA — Customer Trial Audits Pipeline

## What it does
Daily pipeline that tracks Firmable trial customers and checks whether their
company domains exist in the Firmable database. Runs Mon–Fri at 5pm IST.
Every Friday it creates a Linear ticket with the week's missing domains.

## Entry point
```bash
python3 CTA/run_daily.py                    # full run (Playwright + TOTP popup)
python3 CTA/run_daily.py --skip-export      # skip QuickSight export, use latest CSV in ~/Downloads
python3 CTA/run_daily.py --date 2026-06-16  # process a specific date
python3 CTA/run_daily.py --totp 123456      # provide TOTP directly (skip popup)
```

## Pipeline flow
1. **Playwright** exports Master Customers CSV from QuickSight (headless Chromium)
2. **S3 upload** — uploads `MM_DD_CTA.csv` to `s3://fi-firmographics/data_quality/trial_audits/2026/MM/`
3. **TOTP popup** — macOS osascript dialog collects Snowflake MFA code
4. **Snowflake pipeline**:
   - `CTA_raw_input` — raw customer rows, deduplicated by `cta_id`
   - `CTA_staging` — matches domains against `gld_company_core`, enriches with field/people coverage
   - `CTA_summary_by_status` — counts + coverage per `sub_status` per day
   - `CTA_monitoring` — overall daily rollup for QuickSight
5. **Slack** — sends daily summary (blue attachment, no collapse)
6. **Friday only** — queries past 7 days of `NOT_IN_FIRMABLE` domains, creates Linear ticket
   with Excel attachment (`domain`, `first_seen`), includes ticket URL in Slack footer

## Key files
| File | Purpose |
|---|---|
| `run_daily.py` | Main orchestrator — all steps live here |
| `playwright_export.py` | QuickSight headless login + CSV export |
| `config.py` | All table names, S3 paths, constants |
| `src/snowflake_conn.py` | Snowflake connection (password + TOTP) |
| `src/cta_s3_loader.py` | Reads `MM_DD_CTA.csv` from S3 |
| `src/cta_raw_table.py` | Writes to `CTA_raw_input` (pandas write_pandas) |
| `src/cta_staging.py` | Firmable domain match + field/people coverage SQL |
| `src/cta_summary.py` | Summary and monitoring table SQL |

## Snowflake tables
| Table | Purpose |
|---|---|
| `BI.DW.CTA_raw_input` | All raw customer rows, append-only, deduped by `cta_id` |
| `BI.DW.CTA_staging` | Domain-matched rows with Firmable enrichment, idempotent per `run_date` |
| `BI.DW.CTA_summary_by_status` | Daily counts + coverage by `sub_status` |
| `BI.DW.CTA_monitoring` | Daily rollup — used by QuickSight and Slack |

## S3 layout
```
s3://fi-firmographics/data_quality/trial_audits/2026/
  └── MM/
      └── MM_DD_CTA.csv
```

## AWS credentials
CTA uses its own dedicated keys — do NOT use the shared/session credentials:
```
CTA_AWS_ACCESS_KEY_ID
CTA_AWS_SECRET_ACCESS_KEY
```
These are loaded explicitly in `_s3_client()` in `run_daily.py` and `src/cta_s3_loader.py`.

## Cron
```
30 11 * * 1-5   # 11:30 UTC = 5pm IST, Mon–Fri
```
Logs go to `/tmp/cta_daily.log`.

## Linear tickets (Fridays)
- Project: `BAU : Data Releases & Testing : 2026 ( Jan to Dec )`
- Team: `Data & Services`
- Title format: `[CTA] Domains not in Firmable — Week ending YYYY-MM-DD`
- Attachment: Excel file with `domain` + `first_seen` columns
- Priority: Medium

## QuickSight
- Analysis: Master Customers (ap-southeast-2)
- Requires 2560px viewport so the `visual-menu` button at x≈2280 is visible
- Login flow: account name → username → AWS SSO password (`#awsui-input-0`)

## Common issues
| Problem | Fix |
|---|---|
| No rows for today in CSV | Run without `--skip-export` to fetch fresh CSV |
| S3 InvalidToken | Old session token in env — CTA uses `CTA_AWS_*` keys explicitly |
| TOTP expired | Re-enter at popup — TOTP is valid for 30s |
| Slack message collapsed | Already fixed — uses legacy attachment format with `mrkdwn_in` |
