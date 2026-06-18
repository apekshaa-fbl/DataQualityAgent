# Skill 01 — Input Ingestion

## What this stage does
Reads `Master_Customers_.csv` (from S3 or local), filters to active/trialing rows, cleans domains, and writes to `BI.DW.cust_trial_input`.

---

## Stage names
```
STAGE_LOAD      = "load_input"
STAGE_WRITE_RAW = "write_raw_table"
```

---

## Input CSV — Master_Customers_.csv

### Filter rule
Keep only rows where:
```
SUB_STATUS IN ('trialing', 'trialing - pending cancellation', 'active')
```
Everything else is dropped before writing to Snowflake.

### Column map (CSV → Snowflake)
| CSV column | Snowflake column |
|---|---|
| `HUBSPOT_DOMAIN_LINK` | `hubspot_domain_raw` (raw) → `hubspot_domain` (cleaned) |
| `HUBSPOT_NAME` | `hubspot_name` |
| `STRIPE_CUSTOMER_ID` | `stripe_customer_id` |
| `SUB_STATUS` | `sub_status` |
| `PRODUCT_NAME` | `product_name` |
| `STRIPE_BILLING_COUNTRY` | `billing_country` |
| `SEATS` | `seats` |

### Domain cleaning (`clean_domain()` in config.py)
`HUBSPOT_DOMAIN_LINK` may be a bare domain or a HubSpot CRM URL:

| Raw value | Result |
|---|---|
| `fontana.app` | `fontana.app` |
| `https://app.hubspot.com/contacts/...` | `None` — skip |
| `link missing` | `None` — skip |
| `(blank)` | `None` — skip |
| `https://www.acme.com` | `acme.com` (strip protocol + www) |

Rows where `clean_domain()` returns `None` are dropped.

---

## Output table — BI.DW.cust_trial_input

```sql
CREATE TABLE IF NOT EXISTS BI.DW.cust_trial_input (
    trial_id            VARCHAR NOT NULL,   -- MD5(hubspot_domain || run_id)
    run_id              VARCHAR NOT NULL,   -- T26.MM.DD
    run_date            DATE,
    hubspot_domain_raw  VARCHAR,
    hubspot_domain      VARCHAR,            -- cleaned domain
    hubspot_name        VARCHAR,
    stripe_customer_id  VARCHAR,
    sub_status          VARCHAR,
    product_name        VARCHAR,
    billing_country     VARCHAR,
    seats               INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
```

### trial_id
```python
trial_id = MD5(hubspot_domain + run_id)
```
This is the unique key across all pipeline tables.

### Idempotency
INSERT uses `WHERE NOT EXISTS (SELECT 1 ... WHERE trial_id = X AND run_id = Y)`.
Re-running the same run_id never duplicates rows.

---

## S3 source
- Bucket: `fi-firmographics`
- Prefix: `data_quality/trial_audit/input/`
- File: `Master_Customers_YYYY-MM-DD.csv`

## Run ID format
Derived from filename date: `T26.MM.DD`
Example: `Master_Customers_2026-05-27.csv` → `T26.05.27`

---

## Files
- `src/s3_loader.py` — CSV reader + filter + domain cleaning
- `src/raw_table.py` — DDL + INSERT for `cust_trial_input`
- `config.py` — `clean_domain()`, `VALID_SUB_STATUSES`, `make_run_id()`
