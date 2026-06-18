"""
CTA Summary Tables
  - CTA_summary_by_status  : counts + field coverage per sub_status per day
  - CTA_monitoring         : overall daily rollup for QuickSight
Both are append-only, idempotent per run_date (DELETE + INSERT).

Field coverage groups (only for IN_FIRMABLE rows):
  Identity      : name, website
  Social        : linkedin
  Firmographics : industry, founded_year, hq_country
  Size          : employee_count, company_size, revenue
  Contact       : phone, email
"""
import logging

from config import CTA_STAGING_TABLE, CTA_SUMMARY_BY_STATUS_TABLE, CTA_MONITORING_TABLE

logger = logging.getLogger(__name__)

# ── Shared field flags ────────────────────────────────────────────────────────
# One flag per field. Used to compute group coverage and overall avg.
_FIELD_FLAGS = """
    CASE WHEN fbl_name           IS NOT NULL AND TRIM(fbl_name)          != '' THEN 1.0 ELSE 0 END AS f_name,
    CASE WHEN fbl_website        IS NOT NULL AND TRIM(fbl_website)       != '' THEN 1.0 ELSE 0 END AS f_website,
    CASE WHEN fbl_linkedin       IS NOT NULL AND TRIM(fbl_linkedin)      != '' THEN 1.0 ELSE 0 END AS f_linkedin,
    CASE WHEN fbl_industry       IS NOT NULL AND TRIM(fbl_industry)      != '' THEN 1.0 ELSE 0 END AS f_industry,
    CASE WHEN fbl_founded_year   IS NOT NULL                                    THEN 1.0 ELSE 0 END AS f_founded_year,
    CASE WHEN fbl_hq_country     IS NOT NULL AND TRIM(fbl_hq_country)    != '' THEN 1.0 ELSE 0 END AS f_hq_country,
    CASE WHEN fbl_employee_count IS NOT NULL                                    THEN 1.0 ELSE 0 END AS f_employee_count,
    CASE WHEN fbl_company_size   IS NOT NULL AND TRIM(fbl_company_size)  != '' THEN 1.0 ELSE 0 END AS f_company_size,
    CASE WHEN fbl_revenue        IS NOT NULL AND TRIM(fbl_revenue)       != '' THEN 1.0 ELSE 0 END AS f_revenue,
    CASE WHEN fbl_phone          IS NOT NULL AND TRIM(fbl_phone)         != '' THEN 1.0 ELSE 0 END AS f_phone,
    CASE WHEN fbl_email          IS NOT NULL AND TRIM(fbl_email)         != '' THEN 1.0 ELSE 0 END AS f_email,
    firmable_people_count
"""

# ── Group coverage aggregation expressions (for SELECT after flags CTE) ───────
# Each group is covered if ALL fields in the group are present.
_GROUP_COVERAGE = """
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN (f_name + f_website) / 2.0 END) * 100, 2)                          AS identity_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN f_linkedin END) * 100, 2)                                           AS social_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN (f_industry + f_founded_year + f_hq_country) / 3.0 END) * 100, 2) AS firmographics_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN (f_employee_count + f_company_size + f_revenue) / 3.0 END) * 100, 2) AS size_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN (f_phone + f_email) / 2.0 END) * 100, 2)                           AS contact_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN (f_name + f_website + f_linkedin + f_industry + f_founded_year +
              f_hq_country + f_employee_count + f_company_size + f_revenue +
              f_phone + f_email) / 11.0 END) * 100, 2)                          AS avg_field_coverage_pct,
    ROUND(AVG(CASE WHEN in_firmable = 'IN_FIRMABLE'
        THEN CASE WHEN firmable_people_count > 0 THEN 1.0 ELSE 0 END
    END) * 100, 2)                                                               AS people_coverage_pct
"""


# ─────────────────────────────────────────────────────────────────────────────
# CTA_summary_by_status
# ─────────────────────────────────────────────────────────────────────────────

_STATUS_DDL = f"""
CREATE TABLE IF NOT EXISTS {CTA_SUMMARY_BY_STATUS_TABLE} (
    run_date                    DATE,
    run_year                    INTEGER,
    run_quarter                 VARCHAR,
    run_month                   INTEGER,
    run_month_name              VARCHAR,
    sub_status                  VARCHAR,
    total_customers             INTEGER,
    in_firmable_count           INTEGER,
    not_in_firmable_count       INTEGER,
    in_firmable_pct             FLOAT,
    identity_coverage_pct       FLOAT,
    social_coverage_pct         FLOAT,
    firmographics_coverage_pct  FLOAT,
    size_coverage_pct           FLOAT,
    contact_coverage_pct        FLOAT,
    avg_field_coverage_pct      FLOAT,
    people_coverage_pct         FLOAT,
    total_firmable_people       INTEGER,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
"""

_STATUS_INSERT = """
INSERT INTO {status_table}
WITH flags AS (
    SELECT
        run_date, run_year, run_quarter, run_month, run_month_name,
        sub_status, in_firmable,
        {field_flags}
    FROM {staging_table}
    WHERE run_date = '{run_date}'
)
SELECT
    run_date, run_year, run_quarter, run_month, run_month_name,
    sub_status,
    COUNT(*)                                                               AS total_customers,
    SUM(CASE WHEN in_firmable = 'IN_FIRMABLE'     THEN 1 ELSE 0 END)     AS in_firmable_count,
    SUM(CASE WHEN in_firmable = 'NOT_IN_FIRMABLE' THEN 1 ELSE 0 END)     AS not_in_firmable_count,
    ROUND(SUM(CASE WHEN in_firmable = 'IN_FIRMABLE' THEN 1 ELSE 0 END)
          * 100.0 / NULLIF(COUNT(*), 0), 2)                               AS in_firmable_pct,
    {group_coverage},
    SUM(COALESCE(firmable_people_count, 0))                               AS total_firmable_people,
    CURRENT_TIMESTAMP()
FROM flags
GROUP BY run_date, run_year, run_quarter, run_month, run_month_name, sub_status
"""


# ─────────────────────────────────────────────────────────────────────────────
# CTA_monitoring
# ─────────────────────────────────────────────────────────────────────────────

_MONITORING_DDL = f"""
CREATE TABLE IF NOT EXISTS {CTA_MONITORING_TABLE} (
    run_date                    DATE,
    run_year                    INTEGER,
    run_quarter                 VARCHAR,
    run_month                   INTEGER,
    run_month_name              VARCHAR,
    sub_status                  VARCHAR,
    total_customers             INTEGER,
    total_markets               INTEGER,
    in_firmable_count           INTEGER,
    not_in_firmable_count       INTEGER,
    in_firmable_pct             FLOAT,
    identity_coverage_pct       FLOAT,
    social_coverage_pct         FLOAT,
    firmographics_coverage_pct  FLOAT,
    size_coverage_pct           FLOAT,
    contact_coverage_pct        FLOAT,
    avg_field_coverage_pct      FLOAT,
    people_coverage_pct                  FLOAT,
    in_firmable_with_people_count        INTEGER,
    active_in_firmable_count             INTEGER,
    active_not_in_firmable_count         INTEGER,
    active_in_firmable_with_people_count INTEGER,
    total_firmable_people                INTEGER,
    created_at                           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
"""

_MONITORING_INSERT = """
INSERT INTO {monitoring_table}
WITH flags AS (
    SELECT
        run_date, run_year, run_quarter, run_month, run_month_name,
        in_firmable, fbl_hq_country, sub_status,
        {field_flags}
    FROM {staging_table}
    WHERE run_date = '{run_date}'
)
SELECT
    run_date, run_year, run_quarter, run_month, run_month_name,
    sub_status,
    COUNT(*)                                                               AS total_customers,
    COUNT(DISTINCT CASE WHEN fbl_hq_country IS NOT NULL
                        THEN fbl_hq_country END)                           AS total_markets,
    SUM(CASE WHEN in_firmable = 'IN_FIRMABLE'     THEN 1 ELSE 0 END)     AS in_firmable_count,
    SUM(CASE WHEN in_firmable = 'NOT_IN_FIRMABLE' THEN 1 ELSE 0 END)     AS not_in_firmable_count,
    ROUND(SUM(CASE WHEN in_firmable = 'IN_FIRMABLE' THEN 1 ELSE 0 END)
          * 100.0 / NULLIF(COUNT(*), 0), 2)                               AS in_firmable_pct,
    {group_coverage},
    SUM(CASE WHEN in_firmable = 'IN_FIRMABLE'
             AND firmable_people_count > 0 THEN 1 ELSE 0 END)             AS in_firmable_with_people_count,
    SUM(CASE WHEN sub_status = 'active' AND in_firmable = 'IN_FIRMABLE'
             THEN 1 ELSE 0 END)                                            AS active_in_firmable_count,
    SUM(CASE WHEN sub_status = 'active' AND in_firmable = 'NOT_IN_FIRMABLE'
             THEN 1 ELSE 0 END)                                            AS active_not_in_firmable_count,
    SUM(CASE WHEN sub_status = 'active' AND in_firmable = 'IN_FIRMABLE'
             AND firmable_people_count > 0 THEN 1 ELSE 0 END)             AS active_in_firmable_with_people_count,
    SUM(COALESCE(firmable_people_count, 0))                               AS total_firmable_people,
    CURRENT_TIMESTAMP()
FROM flags
GROUP BY run_date, run_year, run_quarter, run_month, run_month_name, sub_status
"""


# ─────────────────────────────────────────────────────────────────────────────
# Runner functions
# ─────────────────────────────────────────────────────────────────────────────

def init_summary_tables(conn) -> None:
    """Create summary tables if they don't exist. Call once per pipeline run."""
    cur = conn.cursor()
    cur.execute(_STATUS_DDL)
    cur.execute(_MONITORING_DDL)
    conn.commit()
    cur.close()


def run_cta_summary_by_status(conn, run_date: str) -> None:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {CTA_SUMMARY_BY_STATUS_TABLE} WHERE run_date = %s", (run_date,))
    sql = _STATUS_INSERT.format(
        status_table=CTA_SUMMARY_BY_STATUS_TABLE,
        staging_table=CTA_STAGING_TABLE,
        field_flags=_FIELD_FLAGS,
        group_coverage=_GROUP_COVERAGE,
        run_date=run_date,
    )
    cur.execute(sql)
    conn.commit()
    cur.close()
    logger.info(f"CTA_summary_by_status updated for run_date={run_date}")


def run_cta_monitoring(conn, run_date: str) -> None:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {CTA_MONITORING_TABLE} WHERE run_date = %s", (run_date,))
    sql = _MONITORING_INSERT.format(
        monitoring_table=CTA_MONITORING_TABLE,
        staging_table=CTA_STAGING_TABLE,
        field_flags=_FIELD_FLAGS,
        group_coverage=_GROUP_COVERAGE,
        run_date=run_date,
    )
    cur.execute(sql)
    conn.commit()
    cur.close()
    logger.info(f"CTA_monitoring updated for run_date={run_date}")
