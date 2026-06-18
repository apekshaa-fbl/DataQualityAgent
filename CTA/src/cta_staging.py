"""
CTA Staging Table — BI.DW.CTA_staging
Main match table: customer domains vs Firmable gold layer.
Append-only, idempotent per run_date (DELETE + INSERT).
Includes year, quarter, month, date columns for QuickSight filtering.
Includes firmable_people_count from gld_people_core.
Coverage rules:
  - company_size / revenue: "No data available" treated as NULL (not covered)
  - industry: NULL or "Unclassified" = not covered
"""
import logging

from config import (
    CTA_RAW_INPUT_TABLE, CTA_STAGING_TABLE,
    FBL_COMPANY_CORE, FBL_COMPANY_DOWNLOAD, FBL_PEOPLE_CORE,
)

logger = logging.getLogger(__name__)

_DDL = f"""
CREATE TABLE IF NOT EXISTS {CTA_STAGING_TABLE} (
    cta_id                  VARCHAR,
    run_date                DATE,
    run_year                INTEGER,
    run_quarter             VARCHAR,
    run_month               INTEGER,
    run_month_name          VARCHAR,
    customer_domain_raw     VARCHAR,
    customer_domain         VARCHAR,
    customer_name           VARCHAR,
    hubspot_name            VARCHAR,
    stripe_customer_id      VARCHAR,
    hubspot_icp             VARCHAR,
    sub_status              VARCHAR,
    product_name            VARCHAR,
    sub_plan_name           VARCHAR,
    sub_plan_interval       VARCHAR,
    sub_plan_amount_aud     FLOAT,
    sub_created             TIMESTAMP,
    stripe_billing_country  VARCHAR,
    seats                   INTEGER,
    in_firmable             VARCHAR,
    fbl_id                  VARCHAR,
    fbl_name                VARCHAR,
    fbl_website             VARCHAR,
    fbl_fqdn                VARCHAR,
    fbl_linkedin            VARCHAR,
    fbl_industry            VARCHAR,
    fbl_founded_year        INTEGER,
    fbl_hq_country          VARCHAR,
    fbl_company_size        VARCHAR,
    fbl_revenue             VARCHAR,
    fbl_employee_count      INTEGER,
    fbl_phone               VARCHAR,
    fbl_email               VARCHAR,
    firmable_people_count   INTEGER,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
"""

_INSERT = """
INSERT INTO {staging_table}
WITH input AS (
    SELECT
        cta_id, run_date,
        YEAR(run_date)                                         AS run_year,
        'Q' || QUARTER(run_date)                               AS run_quarter,
        MONTH(run_date)                                        AS run_month,
        MONTHNAME(run_date)                                    AS run_month_name,
        customer_domain, customer_domain_raw,
        customer_name, hubspot_name,
        stripe_customer_id, hubspot_icp,
        sub_status, product_name, sub_plan_name,
        sub_plan_interval, sub_plan_amount_aud,
        sub_created, stripe_billing_country, seats
    FROM {raw_input_table}
    WHERE run_date = '{run_date}'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY LOWER(TRIM(COALESCE(customer_domain, customer_domain_raw)))
        ORDER BY sub_created DESC
    ) = 1
),
company_dedup AS (
    SELECT *
    FROM {fbl_company_core}
    WHERE id NOT LIKE 'SYNTH_%'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(fqdn)) ORDER BY id) = 1
),
contact_agg AS (
    SELECT firmable_id,
           MAX(primary_phone) AS primary_phone,
           MAX(primary_email) AS primary_email
    FROM {fbl_company_download}
    GROUP BY firmable_id
),
people_agg AS (
    -- Count of people Firmable has indexed per company
    SELECT
        current_company:id::VARCHAR AS fbl_id,
        COUNT(id)                   AS people_count
    FROM {fbl_people_core}
    WHERE current_company:id::VARCHAR IS NOT NULL
    GROUP BY current_company:id::VARCHAR
),
matched AS (
    SELECT
        i.*,
        c.id                               AS fbl_id,
        c.name                             AS fbl_name,
        c.website                          AS fbl_website,
        c.fqdn                             AS fbl_fqdn,
        c.social_media:"linkedin"::VARCHAR AS fbl_linkedin,
        -- industry: NULL or "Unclassified" = not covered
        NULLIF(
            industries[OBJECT_KEYS(industries)[0]::VARCHAR]::VARCHAR,
            'Unclassified'
        )                                  AS fbl_industry,
        c.year_founded::INTEGER            AS fbl_founded_year,
        c.hq_country                       AS fbl_hq_country,
        -- company_size: extract value, treat "No data available" as NULL
        NULLIF(
            company_size[OBJECT_KEYS(company_size)[0]::VARCHAR]::VARCHAR,
            'No data available'
        )                                  AS fbl_company_size,
        -- revenue: extract value, treat "No data available" as NULL
        NULLIF(
            revenue[OBJECT_KEYS(revenue)[0]::VARCHAR]::VARCHAR,
            'No data available'
        )                                  AS fbl_revenue,
        c.employee_count::INTEGER          AS fbl_employee_count,
        ct.primary_phone                   AS fbl_phone,
        ct.primary_email                   AS fbl_email,
        p.people_count                     AS firmable_people_count
    FROM input i
    LEFT JOIN company_dedup c
        ON  i.customer_domain IS NOT NULL
        AND (
            LOWER(TRIM(c.fqdn))   = LOWER(TRIM(i.customer_domain))
            OR c.website LIKE '%' || i.customer_domain || '%'
        )
    LEFT JOIN contact_agg ct ON ct.firmable_id = c.id
    LEFT JOIN people_agg  p  ON p.fbl_id       = c.id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY i.cta_id ORDER BY fbl_id NULLS LAST) = 1
)
SELECT
    cta_id,
    run_date,
    run_year,
    run_quarter,
    run_month,
    run_month_name,
    customer_domain_raw,
    customer_domain,
    customer_name,
    hubspot_name,
    stripe_customer_id,
    hubspot_icp,
    sub_status,
    product_name,
    sub_plan_name,
    sub_plan_interval,
    sub_plan_amount_aud,
    sub_created,
    stripe_billing_country,
    seats,
    CASE WHEN fbl_id IS NOT NULL THEN 'IN_FIRMABLE' ELSE 'NOT_IN_FIRMABLE' END AS in_firmable,
    fbl_id,
    fbl_name,
    fbl_website,
    fbl_fqdn,
    fbl_linkedin,
    fbl_industry,
    fbl_founded_year,
    fbl_hq_country,
    fbl_company_size,
    fbl_revenue,
    fbl_employee_count,
    fbl_phone,
    fbl_email,
    firmable_people_count,
    CURRENT_TIMESTAMP() AS created_at
FROM matched
"""


def init_staging_table(conn) -> None:
    """Create CTA_staging table if it doesn't exist. Call once per pipeline run."""
    cur = conn.cursor()
    cur.execute(_DDL)
    conn.commit()
    cur.close()


def run_cta_staging(conn, run_date: str) -> int:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {CTA_STAGING_TABLE} WHERE run_date = %s", (run_date,))
    deleted = cur.rowcount
    if deleted:
        logger.info(f"Deleted {deleted} existing staging rows for run_date={run_date}")
    sql = _INSERT.format(
        staging_table=CTA_STAGING_TABLE,
        raw_input_table=CTA_RAW_INPUT_TABLE,
        fbl_company_core=FBL_COMPANY_CORE,
        fbl_company_download=FBL_COMPANY_DOWNLOAD,
        fbl_people_core=FBL_PEOPLE_CORE,
        run_date=run_date,
    )
    cur.execute(sql)
    n = cur.rowcount
    conn.commit()
    cur.close()
    logger.info(f"CTA_staging inserted {n} rows for run_date={run_date}")
    return n or 0
