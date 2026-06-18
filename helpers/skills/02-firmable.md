# Skill 02 — Firmable Domain Match

## What this stage does
Matches each trial company's cleaned domain against Firmable's gold layer (`gld_company_core`) to determine whether we have the company in our database. Writes a staging table (`cust_trial_firmable_match`) that all downstream SQL stages read from.

---

## Stage name
```
STAGE_FIRMABLE_SQL = "sql_firmable_match"
```

---

## Match rules

Two match strategies tried in order (LEFT JOIN — one or both may fire):
1. **FQDN exact match**: `LOWER(TRIM(c.FQDN)) = LOWER(TRIM(hubspot_domain))`
2. **Website contains**: `c.WEBSITE LIKE '%' || domain || '%'`

If any match is found → `IN_FIRMABLE`
If no match → `NOT_IN_FIRMABLE`

### Deduplication
If multiple `gld_company_core` rows match the same domain, keep only one:
```sql
QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(FQDN)) ORDER BY ID) = 1
```

### LinkedIn slug
Pulled from `gld_company_core.SOCIAL_MEDIA:linkedin` — **never derived from domain or name**.
If the slug is a full URL (e.g. `https://linkedin.com/company/acme`), strip to bare slug.

---

## Output table — BI.DW.cust_trial_firmable_match

This table is `CREATE OR REPLACE` — rebuilt on every run. Do not use it for append/delta tracking.

Key columns:
| Column | Source |
|---|---|
| `trial_id` | from `cust_trial_input` |
| `run_id` | pipeline run |
| `hubspot_domain` | cleaned domain from input |
| `in_firmable` | `'IN_FIRMABLE'` or `'NOT_IN_FIRMABLE'` |
| `fbl_id` | `gld_company_core.ID` |
| `fbl_name` | `gld_company_core.NAME` |
| `fbl_website` | `gld_company_core.WEBSITE` |
| `fbl_linkedin` | `gld_company_core.SOCIAL_MEDIA:linkedin::VARCHAR` |
| `fbl_industry` | `gld_company_core.INDUSTRIES[0]::VARCHAR` |
| `fbl_founded_year` | `gld_company_core.FOUNDED_YEAR::INTEGER` |
| `fbl_hq_country` | `gld_company_core.HQ_COUNTRY` |
| `fbl_company_type` | `gld_company_core.TYPE` |
| `fbl_phone` | `gld_company_download.PRIMARY_PHONE` |
| `fbl_email` | `gld_company_download.PRIMARY_EMAIL` |

Contact fields (phone/email) come from a grouped subquery on `gld_company_download`:
```sql
SELECT COMPANY_ID, MAX(PRIMARY_PHONE), MAX(PRIMARY_EMAIL)
FROM gld_company_download
GROUP BY COMPANY_ID
```

---

## Firmable gold tables used

| Table | Database.Schema |
|---|---|
| `gld_company_core` | `firmographics.zeus_gold` |
| `gld_company_download` | `firmographics.zeus_gold` |

Filter applied to `gld_company_core`:
```sql
WHERE SOCIAL_MEDIA:linkedin IS NOT NULL
  AND ID NOT LIKE 'SYNTH_%'
```

---

## Downstream reads from this table

Every later SQL stage reads from `cust_trial_firmable_match` for the current `run_id`:
- Stage 6 (field coverage): reads `IN_FIRMABLE` rows + all 9 Firmable field columns
- Stage 7 (people coverage): reads `fbl_id` to JOIN `gld_people_srch`
- Stage 8 (location coverage): reads `fbl_id` to JOIN `gld_company_region`
- Stage 9 (gap summary): indirect (via field/people/location tables)
- Stage 10 (quality score): reads `in_firmable` status
- Stage 11 (NOT_IN_FIRMABLE): reads `NOT_IN_FIRMABLE` rows

---

## Helper functions in firmable_lookup.py

### `run_firmable_match(conn, run_id)`
Runs the full `CREATE OR REPLACE` SQL.

### `get_firmable_summary(conn, run_id)`
Returns `{'IN_FIRMABLE': N, 'NOT_IN_FIRMABLE': N}` for logging.

### `fetch_slugs_for_vetric(conn, run_id)`
Returns list of dicts for IN_FIRMABLE rows that have a non-null `fbl_linkedin_slug`. These are passed to Vetric. Only called before Stage 4.

---

## Anti-rationalization
- **Never derive a slug from the domain or company name.** LinkedIn slug comes exclusively from `SOCIAL_MEDIA:linkedin`.
- **NOT_IN_FIRMABLE rows still get written to cust_trial_firmable_match** — downstream stages need to know these companies exist even if they have no Firmable data.
