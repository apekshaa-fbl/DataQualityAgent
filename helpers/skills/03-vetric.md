# Skill 03 — Vetric API

## What this stage does
Calls the Vetric API for every `IN_FIRMABLE` trial company that has a LinkedIn slug. Stores headcount and office location data for use in people coverage (Stage 7) and location coverage (Stage 8). Results are cached to S3 and written to `cust_trial_input_with_vetric`.

**Phase 1 only uses Vetric for:** headcount + office locations.
Vetric is NOT used for field accuracy in Phase 1.

---

## Stage names
```
STAGE_VETRIC       = "vetric_hit"
STAGE_WRITE_VETRIC = "write_vetric_table"
```

---

## Who gets a Vetric call

Only rows where:
- `in_firmable = 'IN_FIRMABLE'` (from cust_trial_firmable_match)
- `fbl_linkedin_slug IS NOT NULL` (from `gld_company_core.SOCIAL_MEDIA:linkedin`)

Fetched via `firmable_lookup.fetch_slugs_for_vetric(conn, run_id)` before calling Vetric.

---

## LinkedIn slug source

**ONLY `gld_company_core.SOCIAL_MEDIA:linkedin::VARCHAR`.**
Never derive a slug from the domain or company name. Never use a slug from the input CSV.

If the value is a full URL, `normalise_linkedin_slug()` in `config.py` strips it to a bare slug:
```
https://linkedin.com/company/acme → acme
linkedin.com/company/acme         → acme
acme                               → acme
```

---

## API endpoint
```
GET https://api.vetric.io/linkedin/v1/company/{slug}/details
```

---

## Status contract (strict)
| Status | Meaning | Action |
|---|---|---|
| `200` | Found — full JSON returned | Store `vetric_raw`, `vetric_linkedin_slug` |
| `404` | Not found | Store status=404, raw=null |
| `409` | Duplicate slug (Vetric conflict) | Mark before calling — status=409, raw=null |
| `429` | Rate limited | Retry with backoff — never store |
| `500` | Server error | Retry until 200 or 404 — never store |

Never store any status other than 200, 404, 409 in the database.

---

## Vetric fields used in Phase 1

| Vetric JSON path | Used for |
|---|---|
| `:employee_count` | Total headcount → people coverage |
| `:locations[*]:address:country` | Office country list → location coverage |

Always access with `TRY_PARSE_JSON(vetric_raw)` — never direct `:field` syntax on the VARIANT column.

---

## S3 cache
- Bucket: `source-partners`
- Prefix: `companies/source/vetric/2026/trial/`
- One JSON file per slug: `{slug}.json`

S3 is checked before calling the API. If a cached response exists and is 200, it is used directly.

---

## Threading
Vetric calls run with a thread pool (same pattern as QMS `vetric_company.py`).
`fill_all(slug_rows)` mutates the list in place — each row gets `vetric_status`, `vetric_raw`, `vetric_date`, `vetric_linkedin_slug` added.

---

## Output table — BI.DW.cust_trial_input_with_vetric

```sql
CREATE TABLE IF NOT EXISTS BI.DW.cust_trial_input_with_vetric (
    trial_id             VARCHAR NOT NULL,
    run_id               VARCHAR NOT NULL,
    run_date             DATE,
    hubspot_domain       VARCHAR,
    fbl_id               VARCHAR,
    fbl_linkedin_slug    VARCHAR,
    vetric_status        VARCHAR,     -- 200 / 404 / 409
    vetric_date          DATE,
    vetric_raw           VARIANT,     -- full Vetric JSON (200 only), else NULL
    vetric_linkedin_slug VARCHAR,     -- slug from Vetric response (200 only)
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
```

### Idempotency
INSERT uses `WHERE NOT EXISTS (... WHERE trial_id = X AND run_id = Y)`.
Append-only — old runs are preserved.

### vetric_raw storage
Written as `PARSE_JSON(json_string)` — stored as Snowflake VARIANT.
Accessed downstream with `TRY_PARSE_JSON(vetric_raw)` not direct colon syntax.

---

## Files
- `src/vetric_company.py` — API caller + S3 cache + `fill_all()`
- `src/raw_vetric_table.py` — DDL + INSERT for `cust_trial_input_with_vetric`
- `config.py` — `normalise_linkedin_slug()`, `VETRIC_S3_BUCKET`, `VETRIC_S3_PREFIX`
