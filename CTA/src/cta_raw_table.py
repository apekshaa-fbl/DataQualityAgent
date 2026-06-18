"""
CTA Raw Input Table — BI.DW.CTA_raw_input
All customers, all subscription statuses.
Idempotent per cta_id.
"""
import logging
from typing import List

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

from config import CTA_RAW_INPUT_TABLE

logger = logging.getLogger(__name__)

_TABLE    = CTA_RAW_INPUT_TABLE.split(".")[-1].upper()
_DATABASE = "BI"
_SCHEMA   = "DW"

DDL = f"""
CREATE TABLE IF NOT EXISTS {CTA_RAW_INPUT_TABLE} (
    cta_id                                  VARCHAR NOT NULL,
    run_date                                DATE,
    customer_domain_raw                     VARCHAR,
    customer_domain                         VARCHAR,
    customer_name                           VARCHAR,
    hubspot_name                            VARCHAR,
    stripe_customer_id                      VARCHAR,
    hubspot_icp                             VARCHAR,
    sub_status                              VARCHAR,
    product_name                            VARCHAR,
    sub_plan_name                           VARCHAR,
    sub_plan_interval                       VARCHAR,
    sub_plan_amount_aud                     FLOAT,
    sub_created                             TIMESTAMP,
    stripe_billing_country                  VARCHAR,
    available_monthly_subscription_credits  INTEGER,
    hubspot_sales_team_size                 INTEGER,
    stripe_currency                         VARCHAR,
    seats                                   INTEGER,
    loaded_at                               TIMESTAMP,
    s3_file_key                             VARCHAR,
    created_at                              TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
"""


def write_cta_input(conn, rows: List[dict]) -> int:
    if not rows:
        logger.info("No rows to write to CTA_raw_input.")
        return 0

    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()
    cur.close()

    existing_ids = _fetch_existing_cta_ids(conn, rows[0]["run_date"])

    records = []
    for r in rows:
        if r["cta_id"] in existing_ids:
            continue
        records.append({
            "CTA_ID":                                   r["cta_id"],
            "RUN_DATE":                                 r["run_date"],
            "CUSTOMER_DOMAIN_RAW":                      r.get("customer_domain_raw"),
            "CUSTOMER_DOMAIN":                          r.get("customer_domain"),
            "CUSTOMER_NAME":                            r.get("customer_name"),
            "HUBSPOT_NAME":                             r.get("hubspot_name"),
            "STRIPE_CUSTOMER_ID":                       r.get("stripe_customer_id"),
            "HUBSPOT_ICP":                              r.get("hubspot_icp"),
            "SUB_STATUS":                               r.get("sub_status"),
            "PRODUCT_NAME":                             r.get("product_name"),
            "SUB_PLAN_NAME":                            r.get("sub_plan_name"),
            "SUB_PLAN_INTERVAL":                        r.get("sub_plan_interval"),
            "SUB_PLAN_AMOUNT_AUD":                      r.get("sub_plan_amount_aud"),
            "SUB_CREATED":                              r.get("sub_created"),
            "STRIPE_BILLING_COUNTRY":                   r.get("stripe_billing_country"),
            "AVAILABLE_MONTHLY_SUBSCRIPTION_CREDITS":   r.get("available_monthly_subscription_credits"),
            "HUBSPOT_SALES_TEAM_SIZE":                  r.get("hubspot_sales_team_size"),
            "STRIPE_CURRENCY":                          r.get("stripe_currency"),
            "SEATS":                                    r.get("seats"),
            "LOADED_AT":                                r.get("loaded_at"),
            "S3_FILE_KEY":                              r.get("s3_file_key"),
        })

    if not records:
        logger.info("All rows already exist in CTA_raw_input — skipping insert.")
        return 0

    df = pd.DataFrame(records)
    success, _, n_rows, _ = write_pandas(
        conn, df, _TABLE,
        database=_DATABASE, schema=_SCHEMA,
        auto_create_table=False,
        overwrite=False,
        quote_identifiers=False,
    )
    if not success:
        raise RuntimeError(f"write_pandas failed for {CTA_RAW_INPUT_TABLE}")

    logger.info(f"Inserted {n_rows} rows into {CTA_RAW_INPUT_TABLE}")
    return n_rows


def _fetch_existing_cta_ids(conn, run_date: str) -> set:
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT cta_id FROM {CTA_RAW_INPUT_TABLE} WHERE run_date = %s",
            (run_date,)
        )
        return {row[0] for row in cur.fetchall()}
    except Exception:
        return set()
    finally:
        cur.close()
