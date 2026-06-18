# Skill 05 — People Coverage

## What this stage does
For each `IN_FIRMABLE` trial company, counts how many people Firmable has per market and compares to Vetric's reported total headcount. Produces a per-market people coverage percentage and a people gap.

---

## Stage names
```
STAGE_PEOPLE_DDL    = "sql_people_ddl"
STAGE_PEOPLE_INSERT = "sql_people_insert"
```

---

## Logic

### Firmable side — per market
```sql
SELECT
    m.trial_id, m.fbl_id, m.hubspot_domain,
    ps.COUNTRY_CODE AS market,
    COUNT(*) AS firmable_people_count
FROM cust_trial_firmable_match m
JOIN firmographics.zeus_gold.gld_people_srch ps
    ON ps.COMPANY_ID = m.fbl_id
   AND ps.COUNTRY_CODE IN ('AU','NZ','MY','SG','HK','JP','ID','PH','US','CA')
WHERE m.run_id = '{run_id}' AND m.in_firmable = 'IN_FIRMABLE'
GROUP BY m.trial_id, m.fbl_id, m.hubspot_domain, ps.COUNTRY_CODE
```

### Vetric side — total headcount (not per market)
```sql
TRY_CAST(TRY_PARSE_JSON(vetric_raw):employee_count::VARCHAR AS INTEGER)
```
Pulled from `cust_trial_input_with_vetric` where `vetric_status = '200'`.

Vetric provides a company-level headcount total, not broken down by country. This is used as the denominator for every market row (i.e., "how much of the total LinkedIn headcount does Firmable have indexed in this market?").

### Coverage calculation
```sql
people_coverage_pct = LEAST(GREATEST(ROUND(
    firmable_people_count * 100.0 / NULLIF(vetric_headcount, 0)
, 2), 0), 100)

people_gap = GREATEST(vetric_headcount - firmable_people_count, 0)
```

If Vetric returned no data (404/409 or null headcount): `vetric_headcount = 0`, `people_coverage_pct = NULL`.

---

## Output table — BI.DW.cust_trial_people_coverage

Append-only (`CREATE TABLE IF NOT EXISTS` + INSERT).

```sql
trial_id              VARCHAR NOT NULL
run_id                VARCHAR NOT NULL
run_date              DATE
hubspot_domain        VARCHAR
fbl_id                VARCHAR
market                VARCHAR(2)       -- one of 10 markets
firmable_people_count INTEGER          -- how many people Firmable has in this market
vetric_headcount      INTEGER          -- Vetric total (same value across all market rows for this company)
employee_coverage_pct FLOAT            -- same as people_coverage_pct (kept separate for clarity)
people_coverage_pct   FLOAT            -- 0–100, capped
people_gap            INTEGER          -- vetric_headcount - firmable_people_count (floored 0)
created_at            TIMESTAMP
```

### Idempotency
```sql
WHERE NOT EXISTS (
    SELECT 1 FROM BI.DW.cust_trial_people_coverage
    WHERE trial_id = combined.trial_id
      AND run_id   = '{run_id}'
      AND market   = combined.market
)
```

---

## Markets in scope
```
AU · NZ · MY · SG · HK · JP · ID · PH · US · CA
```
Only markets where Firmable has at least one person for the company generate a row.

---

## Rules
- Every division uses `NULLIF(vetric_headcount, 0)`. No exceptions.
- `people_coverage_pct` is capped at 100 with `LEAST(..., 100)`. If Firmable has more indexed people than Vetric reports, that's still 100%.
- `people_gap` floored at 0 — never negative.
- Companies with no Vetric data (404/409) still get rows if Firmable has people — with `vetric_headcount = 0` and `people_coverage_pct = NULL`.

---

## File
- `src/sql_steps.py` → `SQL_PEOPLE_DDL`, `SQL_PEOPLE_INSERT`, `run_people_ddl(conn)`, `run_people_insert(conn, run_id, run_date)`
