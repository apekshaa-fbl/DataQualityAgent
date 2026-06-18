# Data Quality Agents — Workspace

## Overview
This repo contains Firmable's internal data quality automation pipelines.
Each project lives in its own top-level folder and is fully self-contained.

## Projects
| Folder | Purpose | Entry point |
|---|---|---|
| `CTA/` | Customer Trial Audits — daily pipeline, Slack, Linear | `CTA/run_daily.py` |
| `QMS/` | Quality Monitoring System — company + people coverage | `QMS/company/run.py`, `QMS/people/run.py` |
| `EMAIL/` | Email Data Quality — weekly coverage/accuracy/consistency across 13 markets | QuickSight dashboard |

## Shared layout
```
Data_Quality_Agents/
├── .env                  # all secrets (never commit)
├── CLAUDE.md             # this file
├── CTA/                  # Customer Trial Audits pipeline
├── QMS/                  # Quality Monitoring System
└── helpers/              # local docs & skills — gitignored, not for repo
```

## Environment variables (`.env`)
| Key | Used by |
|---|---|
| `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE` | All pipelines |
| `CTA_AWS_ACCESS_KEY_ID`, `CTA_AWS_SECRET_ACCESS_KEY` | CTA S3 operations only |
| `SLACK_WEBHOOK_URL` | CTA Slack notifications |
| `LINEAR_API_KEY` | CTA Friday Linear tickets |
| `QUICKSIGHT_ACCOUNT`, `QUICKSIGHT_USERNAME`, `QUICKSIGHT_PASSWORD` | CTA Playwright export |
| `SUPABASE_URL`, `SUPABASE_KEY` | QMS Supabase upsert |

## Git conventions (Firmable standard)
- Branch format: `feature/<task-id>/<name>` or `chore/...` or `hotfix/...`
- Commit prefixes: `[ADD]` `[MOD]` `[DEL]` `[WIP]`
- Never commit `.env`, `*.p8`, `*.pub`, `helpers/`
- Active branch: `feature/cta-daily-pipeline`

## Snowflake
- Database: `BI`, Schema: `DW`
- Auth: password + TOTP MFA (macOS popup via osascript)
- CTA tables: `BI.DW.CTA_raw_input`, `BI.DW.CTA_staging`, `BI.DW.CTA_summary_by_status`, `BI.DW.CTA_monitoring`
- QMS tables: `BI.RAW.DQMS_COMP_RAW_DATA`, `BI.RAW.dqms_ppl_raw_data`

## Adding a new project
Create a new folder at the root (e.g. `SIGNALS/`) following the same pattern:
- `config.py` — all constants
- `run.py` or `run_daily.py` — entry point
- `src/` — pipeline modules
- Add a `CLAUDE.md` inside the folder
