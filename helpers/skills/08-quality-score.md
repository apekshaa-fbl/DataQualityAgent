# Skill 08 — Quality Score + Dashboard Views

## What this stage does
Computes the final quality score per company per market (simple average of 3 coverage dimensions). Also handles NOT_IN_FIRMABLE companies (score = 0). Creates 3 dashboard views.

---

## Stage names
```
STAGE_QUALITY_DDL    = "sql_quality_ddl"
STAGE_QUALITY_INSERT = "sql_quality_insert"
STAGE_NOT_IN_FBL     = "sql_not_in_fbl_insert"
STAGE_VIEW_OVERALL   = "sql_view_overall"
STAGE_VIEW_MARKET    = "sql_view_by_market"
STAGE_VIEW_DASHBOARD = "sql_view_dashboard"
```

---

## Quality Score Formula

```
quality_score = AVG(field_coverage_pct, people_coverage_pct, location_coverage_pct)
             = (field_coverage_pct + people_coverage_pct + location_coverage_pct) / 3.0
```

All three inputs are already 0–100. Result is capped 0–100.

**No weighting. Simple average. Phase 1 only.**

```sql
LEAST(GREATEST(ROUND((
    g.field_coverage_pct +
    COALESCE(g.people_coverage_pct, 0) +
    COALESCE(g.location_coverage_pct, 0)
) / 3.0, 2), 0), 100) AS quality_score
```

---

## Quality bands
| Score range | Status |
|---|---|
| 90–100 | `EXCELLENT` |
| 75–89 | `GOOD` |
| 60–74 | `FAIR` |
| 40–59 | `NEEDS WORK` |
| 0–39 | `POOR` |

---

## Delta tracking
```sql
quality_delta = ROUND(current_quality_score - prev_quality_score, 2)
```
`prev_quality_score` = latest quality score for this `(trial_id, market)` from any prior run (not the current `run_id`).

```
direction:
  IMPROVED  — delta > +2
  DECLINED  — delta < -2
  STABLE    — delta within ±2
  FIRST_RUN — no prior run found (prev_quality_score IS NULL)
```

---

## NOT_IN_FIRMABLE companies (Stage 11)

Companies not found in Firmable get a separate INSERT with fixed values:
```python
quality_score         = 0
quality_status        = 'POOR'
direction             = 'FIRST_RUN'
field_coverage_pct    = 0
people_coverage_pct   = 0
location_coverage_pct = 0
fields_missing_count  = 9
missing_fields        = NULL
people_gap            = 0
location_gap_count    = 0
fbl_id                = NULL
market                = NULL
```

---

## Output table — BI.DW.cust_trial_quality_score

Append-only (`CREATE TABLE IF NOT EXISTS` + INSERT).

```sql
trial_id                VARCHAR NOT NULL
run_id                  VARCHAR NOT NULL
run_date                DATE
hubspot_domain          VARCHAR
hubspot_name            VARCHAR
stripe_customer_id      VARCHAR
fbl_id                  VARCHAR          -- NULL for NOT_IN_FIRMABLE
in_firmable             VARCHAR          -- 'IN_FIRMABLE' or 'NOT_IN_FIRMABLE'
market                  VARCHAR(2)       -- NULL for NOT_IN_FIRMABLE
field_coverage_pct      FLOAT
people_coverage_pct     FLOAT
location_coverage_pct   FLOAT
quality_score           FLOAT            -- 0–100
quality_status          VARCHAR          -- EXCELLENT/GOOD/FAIR/NEEDS WORK/POOR
prev_run_id             VARCHAR
prev_quality_score      FLOAT
quality_delta           FLOAT            -- NULL on first run
direction               VARCHAR          -- IMPROVED/DECLINED/STABLE/FIRST_RUN
fields_missing_count    INTEGER
missing_fields          VARIANT
people_gap              INTEGER
location_gap_count      INTEGER
created_at              TIMESTAMP
```

### Idempotency (IN_FIRMABLE rows)
```sql
WHERE NOT EXISTS (
    SELECT 1 FROM BI.DW.cust_trial_quality_score
    WHERE trial_id = s.trial_id AND run_id = '{run_id}' AND market = s.market
)
```

---

## Dashboard Views

### 1. cust_trial_overall_run_v
Run-level summary — one row per `run_id`:
- `companies_audited`, `in_firmable_count`, `not_in_firmable_count`, `in_firmable_pct`
- `avg_quality_score` (IN_FIRMABLE only)
- Band counts: `excellent_count`, `good_count`, `fair_count`, `needs_work_count`, `poor_count`
- Direction counts: `improved_count`, `declined_count`, `stable_count`, `first_run_count`

### 2. cust_trial_by_market_v
Per market summary — one row per `(run_id, market)`:
- `companies`, `avg_quality_score`
- `avg_field_coverage`, `avg_people_coverage`, `avg_location_coverage`
- `total_people_gap`, `total_location_gaps`

### 3. cust_trial_dashboard_v
Full row-level view — one row per company per market:
- All quality score columns
- Joined with `cust_trial_input` for: `icp`, `product_name`, `plan_amount_aud`, `billing_country`, `seats`

---

## Rules
- All three coverage inputs default to 0 (not NULL) before averaging — `COALESCE(..., 0)`.
- Quality score capped 0–100 using `LEAST(GREATEST(...), 100)`.
- Delta direction threshold is ±2 (not ±1 or ±5).
- Views are `CREATE OR REPLACE` — rebuilt every run.
- Do not add accuracy, Pubrio, or weighted scoring. Phase 1 = simple average of 3 dimensions.

---

## File
- `src/sql_steps.py` → all SQL constants + runner functions
