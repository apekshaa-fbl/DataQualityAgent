# Skill 04 — Field Coverage

## What this stage does
Checks whether each of the 9 core Firmable fields is populated for every `IN_FIRMABLE` trial company. Computes a field coverage percentage and a list of missing fields. **Phase 1 only — no comparison to Vetric or LinkedIn.**

---

## Stage name
```
STAGE_FIELD_COVERAGE = "sql_field_coverage"
```

---

## Source table
`BI.DW.cust_trial_firmable_match` — filtered to `in_firmable = 'IN_FIRMABLE'` and current `run_id`.

---

## 9 Fields Checked

All fields come from Firmable gold tables. Coverage = is the field populated in Firmable? (Yes/No — no comparison to external source.)

| # | Snowflake column | Flag column |
|---|---|---|
| 1 | `fbl_name` (`gld_company_core.NAME`) | `name_covered` |
| 2 | `fbl_website` (`gld_company_core.WEBSITE`) | `website_covered` |
| 3 | `fbl_linkedin` (`gld_company_core.SOCIAL_MEDIA:linkedin`) | `linkedin_covered` |
| 4 | `fbl_industry` (`gld_company_core.INDUSTRIES[0]`) | `industry_covered` |
| 5 | `fbl_founded_year` (`gld_company_core.FOUNDED_YEAR`) | `founded_year_covered` |
| 6 | `fbl_hq_country` (`gld_company_core.HQ_COUNTRY`) | `hq_country_covered` |
| 7 | `fbl_company_type` (`gld_company_core.TYPE`) | `company_type_covered` |
| 8 | `fbl_phone` (`gld_company_download.PRIMARY_PHONE`) | `phone_covered` |
| 9 | `fbl_email` (`gld_company_download.PRIMARY_EMAIL`) | `email_covered` |

**Coverage rule:** `1` if field IS NOT NULL AND TRIM(field) != ''  (except `founded_year` — numeric, only NULL check)
**NOT covered:** `0`

---

## Field coverage %
```sql
field_coverage_pct = ROUND(SUM(covered_flags) * 100.0 / 9, 2)
```
Capped 0–100.

---

## Missing fields array
```sql
missing_fields = ARRAY_COMPACT(ARRAY_CONSTRUCT(
    CASE WHEN fbl_name IS NULL OR TRIM(fbl_name) = '' THEN 'name' END,
    CASE WHEN fbl_website IS NULL OR TRIM(fbl_website) = '' THEN 'website' END,
    ...
))
```
VARIANT column. Empty array = all 9 fields populated.

---

## Output table — BI.DW.cust_trial_field_coverage

`CREATE OR REPLACE` — rebuilt every run. Does not accumulate history.

```sql
CREATE OR REPLACE TABLE BI.DW.cust_trial_field_coverage AS
SELECT
    trial_id, run_id, run_date, hubspot_domain, hubspot_name,
    in_firmable, fbl_id,
    -- 9 binary flags
    name_covered, website_covered, linkedin_covered, industry_covered,
    founded_year_covered, hq_country_covered, company_type_covered,
    phone_covered, email_covered,
    -- summary
    field_coverage_pct,   -- FLOAT, 0–100
    missing_fields,       -- VARIANT array of field name strings
    created_at
FROM ...
```

---

## Rules
- Only `IN_FIRMABLE` rows. `NOT_IN_FIRMABLE` companies are not processed here — they get `field_coverage_pct = 0` in Stage 10 (quality score insert).
- No Vetric data used. No accuracy comparison. Phase 1 = coverage only.
- Every division uses `NULLIF(denominator, 0)` — the 9 is a literal constant here but the pattern is enforced everywhere else in the pipeline.

---

## File
- `src/sql_steps.py` → `SQL_FIELD_COVERAGE` + `run_field_coverage(conn, run_id)`
