# EMAIL — Email Data Quality Pipeline

## What it does
Measures email coverage, accuracy, and consistency across 13 Firmable markets.
Data refreshes weekly via a Snowflake stored procedure, surfaced in a QuickSight dashboard.

## Markets
AU, NZ, MY, SG, HK, JP, ID, PH, US, CA, TH, VN, KR

## Schedule
- **Snowflake Task** `SP_REFRESH_EMAIL_QUALITY_SUMMARY` runs: **Friday 6 PM IST** *(not yet created — pending)*
- **QuickSight SPICE refresh**: **Friday 7:30 PM IST** (after Snowflake task completes)

## Source tables
| Table | Role | Notes |
|---|---|---|
| `FIRMOGRAPHICS.ZEUS_GOLD.GLD_COMPANY_DOWNLOAD` | Primary source | Gold layer — `ID` (region record), `FIRMABLE_ID` (global distinct company), `REGION_CODE`, `PRIMARY_EMAIL`, `OTHER_EMAILS`, `FQDN`, `GLOBAL_EMP_COUNT` |
| `FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY` | Deliverability | `SLUG` = gold `ID`; `DELIVERABILITY` values: `em-av-likely`, `em-av-highly-likely`, `em-av-unsure`, `em-av-undeliverable`, or empty. **Note:** join returns all zeros — slug alignment issue, removed from current analysis |

## Output tables (Snowflake — to be created)
| Table | Purpose | Rows/week |
|---|---|---|
| `BI.DW.DQ_EMAIL_GLOBAL_SUMMARY` | Global counts + quality score (Coverage/Accuracy/Consistency) | 1 |
| `BI.DW.DQ_EMAIL_QUALITY_SUMMARY` | Country-level metrics, full history | 13 |
| `BI.DW.DQ_EMAIL_QUALITY_DELTA` | Week-over-week changes per issue per country | 91 |
| `BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN` | Email count by source × country | varies |

## Key counts (from gold layer, as of last query)
- **15.1M** — distinct companies (`COUNT(DISTINCT FIRMABLE_ID)`)
- **168.8M** — total company-country records (`COUNT(ID)`) across all 13 markets

## Quality dimensions
| Dimension | Definition | Signals |
|---|---|---|
| Coverage | % companies with at least one email (primary or other) | `HAS_EMAIL` |
| Accuracy | Weighted composite score across 5 signals | Domain match 40%, Not duplicate 20%, Not blocked 20%, Not free provider (50+ emp) 15%, Valid format 5% |
| Consistency | % emails that are valid format and not blocked | `FORMAT_STATUS = 'valid'` + `IS_BLOCKED = 0` |
| Overall | Weighted quality score (0–100) | Coverage 40% + Accuracy 40% + Consistency 20% |

## Issues tracked per country
| Category | Issue | Fix impact |
|---|---|---|
| Coverage | Missing Email | ↑ Coverage |
| Coverage | Domain Gap (has FQDN but no email) | ↑ Coverage |
| Accuracy | Domain Mismatch | ↑ Accuracy |
| Accuracy | Invalid Format | ↑ Accuracy + Consistency |
| Accuracy | No Deliverability Check | ↑ Accuracy |
| Accuracy | Cross-Company Duplicate Email | ↑ Accuracy |
| Noise | Blocked / No-Reply | ↑ Accuracy + Consistency |
| Noise | Free Provider (50+ emp) | ↑ Accuracy |
| Noise | Generic Role-Based | ↑ Consistency |

## Top 5 email scoring (per company)
Emails are scored 0–9 and ranked. Top 5 are kept; all are listed if fewer than 5 exist.

| Signal | Points |
|---|---|
| Domain matches company FQDN root | +3 |
| Not a free provider (gmail, yahoo, etc.) | +2 |
| Not blocked (noreply, do-not-reply) | +2 |
| Valid email format | +1 |
| Not a cross-company duplicate | +1 |
| Micro bonus: ≤10 emp with free provider | +1 |

Company size bands (using `GLOBAL_EMP_COUNT`): micro ≤10, SMB 11–50, mid/enterprise 51+

## Company size awareness
Free provider emails (gmail, yahoo, etc.) are penalised only for companies with 50+ employees.
For micro companies (≤10 emp), free provider emails get a +1 bonus as they are expected.

## SQL — main analysis query
Core query lives in the session history (see JSONL). Key CTEs:
1. `base` — joins gold table, extracts email domain/local/root
2. `dup_emails` — finds emails shared across multiple `FIRMABLE_ID`s (cross-company duplicates)
3. `flagged` — applies all signal flags: `FORMAT_STATUS`, `IS_FREE_PROVIDER`, `IS_BLOCKED`, `IS_GENERIC`, `IS_DOMAIN_MATCH`, `IS_DOMAIN_MISMATCH`, `IS_DUPLICATE_EMAIL`
4. Final `SELECT` — groups by `REGION_CODE`, computes all counts and percentages

**Snowflake syntax notes:**
- Use `RLIKE(...)` not `~` (PostgreSQL syntax)
- `REGEXP_REPLACE` without `'g'` flag — Snowflake replaces all by default
- Root domain comparison: `SPLIT_PART(FQDN, '.', 1)` vs `SPLIT_PART(email_domain, '.', 1)`

## Key docs
| File | Purpose |
|---|---|
| `quicksight.md` | Full QuickSight build guide (datasets, visuals, SQL, checklist) |
| `dashboard_mockup.html` | Interactive HTML mockup — 4 tabs: Overview, Issues Analysis, Top 5 Email Logic, Quality Trends. Use for CEO-level presentations. |

## Status
| Item | Status |
|---|---|
| Gold layer source confirmed | ✅ Done |
| Analysis SQL written | ✅ Done |
| HTML dashboard mockup | ✅ Done (8 Top 5 scenarios, weighted accuracy, fix impact notes) |
| Stored procedure `SP_REFRESH_EMAIL_QUALITY_SUMMARY` | ⏳ Not started |
| Top 5 email scoring SQL | ⏳ Not started |
| Output tables created in Snowflake | ⏳ Not started |
| QuickSight dashboard built | ⏳ Not started |
