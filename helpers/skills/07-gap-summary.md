# Skill 07 — Gap Summary

## What this stage does
Joins field coverage, people coverage, and location coverage into a single summary table per company per market. This is the input table for the quality score calculation.

---

## Stage name
```
STAGE_GAP_SUMMARY = "sql_gap_summary"
```

---

## Source tables
| Table | What it contributes |
|---|---|
| `cust_trial_field_coverage` | `field_coverage_pct`, `fields_missing_count`, `missing_fields` (company level) |
| `cust_trial_people_coverage` | `firmable_people_count`, `vetric_headcount`, `people_gap`, `people_coverage_pct` (per market) |
| `cust_trial_location_coverage` | `in_firmable_at_location`, `vetric_has_location`, `location_gap`, `location_coverage_pct` (per market) |

---

## Join structure

Field coverage is company-level (one row per company). People and location are market-level (one row per company per market). The join fans out field coverage to each market row.

```sql
field_gaps  LEFT JOIN people_gaps   ON trial_id, run_id
            LEFT JOIN location_gaps ON trial_id, run_id, market
```

`location_coverage_pct` is computed using a window function inside the `location_gaps` CTE (% of Vetric locations that Firmable also has).

---

## Location coverage % (computed here)
```sql
location_coverage_pct = ROUND(
    SUM(CASE WHEN in_firmable_at_location THEN 1 ELSE 0 END)
    OVER (PARTITION BY trial_id, run_id) * 100.0
    / NULLIF(
        SUM(CASE WHEN vetric_has_location THEN 1 ELSE 0 END)
        OVER (PARTITION BY trial_id, run_id)
    , 0)
, 2)
```

---

## Output table — BI.DW.cust_trial_gap_summary

`CREATE OR REPLACE` — rebuilt every run. Not append-only.

```sql
trial_id                VARCHAR
run_id                  VARCHAR
run_date                DATE
hubspot_domain          VARCHAR
fbl_id                  VARCHAR
market                  VARCHAR(2)       -- NULL if company has no market rows

-- Coverage gap (field level)
field_coverage_pct      FLOAT            -- from field_coverage
fields_missing_count    INTEGER          -- 9 minus covered count
missing_fields          VARIANT          -- array of missing field names

-- People gap (per market)
firmable_people_count   INTEGER
vetric_headcount        INTEGER
people_gap              INTEGER          -- vetric_headcount - firmable_people_count (≥ 0)
people_coverage_pct     FLOAT            -- 0–100

-- Location gap (per market)
in_firmable_at_location BOOLEAN
vetric_has_location     BOOLEAN
location_gap            BOOLEAN          -- TRUE = Vetric has it, Firmable doesn't
location_coverage_pct   FLOAT            -- 0–100, computed with window function

created_at              TIMESTAMP
```

---

## Defaults for null joins
```sql
COALESCE(p.firmable_people_count, 0)       -- no Vetric / no people
COALESCE(p.people_gap, 0)
COALESCE(p.people_coverage_pct, 0)
COALESCE(l.location_coverage_pct, 0)
COALESCE(l.in_firmable_at_location, FALSE)
COALESCE(l.vetric_has_location, FALSE)
COALESCE(l.location_gap, FALSE)
```

---

## Rules
- Every division uses `NULLIF(denominator, 0)`. The `location_coverage_pct` window function uses `NULLIF` on the vetric location count denominator.
- `field_coverage_pct` flows unchanged from Stage 6.
- The quality score (Stage 10) reads directly from this table.

---

## File
- `src/sql_steps.py` → `SQL_GAP_SUMMARY`, `run_gap_summary(conn, run_id)`
