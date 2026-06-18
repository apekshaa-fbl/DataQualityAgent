# Skill 06 — Location Coverage

## What this stage does
Compares Vetric's list of office countries to Firmable's list of countries (from `gld_company_region`). For each market where either source has a presence, records whether Firmable also has it. A `location_gap = TRUE` means Vetric has an office in that country but Firmable does not.

---

## Stage names
```
STAGE_LOCATION_DDL    = "sql_location_ddl"
STAGE_LOCATION_INSERT = "sql_location_insert"
```

---

## Logic

### Vetric side — extract all office countries
```sql
WITH vetric_locations AS (
    SELECT
        v.trial_id,
        UPPER(TRIM(loc.value:address:country::VARCHAR)) AS vetric_country
    FROM BI.DW.cust_trial_input_with_vetric v,
         LATERAL FLATTEN(
             INPUT => TRY_PARSE_JSON(v.vetric_raw):locations,
             OUTER => TRUE
         ) loc
    WHERE v.run_id = '{run_id}'
      AND v.vetric_status = '200'
      AND loc.value:address:country IS NOT NULL
)
```

Then deduplicate to one row per `(trial_id, vetric_country)` and filter to 10 markets:
```sql
vetric_markets AS (
    SELECT DISTINCT trial_id, vetric_country AS market
    FROM vetric_locations
    WHERE vetric_country IN ('AU','NZ','MY','SG','HK','JP','ID','PH','US','CA')
)
```

### Firmable side — countries from gld_company_region
```sql
firmable_markets AS (
    SELECT DISTINCT m.trial_id, m.fbl_id, m.hubspot_domain, cr.COUNTRY_CODE AS market
    FROM cust_trial_firmable_match m
    JOIN firmographics.zeus_gold.gld_company_region cr
        ON cr.COMPANY_ID = m.fbl_id
       AND cr.COUNTRY_CODE IN ('AU','NZ','MY','SG','HK','JP','ID','PH','US','CA')
    WHERE m.run_id = '{run_id}' AND m.in_firmable = 'IN_FIRMABLE'
)
```

### Union both sources → all_markets
```sql
all_markets AS (
    SELECT trial_id, fbl_id, hubspot_domain, market FROM firmable_markets
    UNION
    SELECT vm.trial_id, fm.fbl_id, fm.hubspot_domain, vm.market
    FROM vetric_markets vm
    JOIN cust_trial_firmable_match fm ON fm.trial_id = vm.trial_id AND fm.run_id = '{run_id}'
)
```

### Final JOIN to compute flags
```sql
in_firmable_at_location = (firmable_markets.market IS NOT NULL)
vetric_has_location     = (vetric_markets.market IS NOT NULL)
location_gap            = vetric has it AND Firmable doesn't
                        = (vetric_has_location AND NOT in_firmable_at_location)
```

---

## Output table — BI.DW.cust_trial_location_coverage

Append-only (`CREATE TABLE IF NOT EXISTS` + INSERT).

```sql
trial_id                VARCHAR NOT NULL
run_id                  VARCHAR NOT NULL
run_date                DATE
hubspot_domain          VARCHAR
fbl_id                  VARCHAR
market                  VARCHAR(2)   -- one row per company per market seen in either source
in_firmable_at_location BOOLEAN      -- TRUE if gld_company_region has this country
vetric_has_location     BOOLEAN      -- TRUE if Vetric :locations has this country
location_gap            BOOLEAN      -- TRUE if vetric_has_location AND NOT in_firmable_at_location
created_at              TIMESTAMP
```

### Idempotency
```sql
WHERE NOT EXISTS (
    SELECT 1 FROM BI.DW.cust_trial_location_coverage
    WHERE trial_id = a.trial_id AND run_id = '{run_id}' AND market = a.market
)
```

---

## Location coverage % (computed in Stage 9 — Gap Summary)

Location coverage is not computed in this table — it is computed in `cust_trial_gap_summary`:
```sql
location_coverage_pct = ROUND(
    SUM(CASE WHEN in_firmable_at_location THEN 1 ELSE 0 END) OVER (PARTITION BY trial_id, run_id)
    * 100.0
    / NULLIF(SUM(CASE WHEN vetric_has_location THEN 1 ELSE 0 END) OVER (PARTITION BY trial_id, run_id), 0)
, 2)
```

---

## Rules
- `LATERAL FLATTEN` with `OUTER => TRUE` — if `:locations` is null or empty, the row is included with null values (filtered out by `loc.value:address:country IS NOT NULL`).
- Always `TRY_PARSE_JSON(vetric_raw)` — never direct VARIANT colon syntax on the stored column.
- All country codes uppercased and trimmed before filtering to the 10 markets.
- `NULLIF(denominator, 0)` on all divisions — enforced in gap summary.

---

## File
- `src/sql_steps.py` → `SQL_LOCATION_DDL`, `SQL_LOCATION_INSERT`, `run_location_ddl(conn)`, `run_location_insert(conn, run_id, run_date)`
