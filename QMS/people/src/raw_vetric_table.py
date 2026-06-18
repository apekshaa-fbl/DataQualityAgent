"""
Raw Vetric Table Writer — BI.RAW.dqms_ppl_inp_with_vetric
Stores input fields + Vetric response data.
Idempotent per s3_file_key (delete + re-insert).

Critical: vetric_raw is stored as a JSON string — Snowflake stores it as string-type VARIANT.
Always use TRY_PARSE_JSON(VETRIC_RAW):field in SQL (never VETRIC_RAW:field directly).
"""
import json
import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

from config import RAW_VETRIC_TABLE

logger = logging.getLogger(__name__)

_TABLE    = RAW_VETRIC_TABLE.split(".")[-1].upper()
_DATABASE = "BI"
_SCHEMA   = "RAW"

DDL = f"""
CREATE TABLE IF NOT EXISTS {RAW_VETRIC_TABLE} (
    run_id              VARCHAR,
    row_id              VARCHAR,
    s3_file_key         VARCHAR,
    file_date           DATE,
    loaded_at           TIMESTAMP,
    source              VARCHAR,
    inp_criteria        VARCHAR,
    inp_full_name       VARCHAR,
    inp_first_name      VARCHAR,
    inp_last_name       VARCHAR,
    inp_title           VARCHAR,
    inp_company         VARCHAR,
    inp_location        VARCHAR,
    inp_domain          VARCHAR,
    inp_linkedin        VARCHAR,
    inp_country         VARCHAR,
    inp_linkedin_slug   VARCHAR,
    vetric_status       VARCHAR,
    vetric_date         DATE,
    vetric_raw          VARIANT,
    created_at          TIMESTAMP
)
"""


def write_raw_vetric(conn, rows: List[dict]) -> int:
    if not rows:
        logger.info("No rows to write to raw vetric table.")
        return 0

    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()

    # Idempotent: delete existing rows for this file key before re-inserting
    file_keys = list({r["s3_file_key"] for r in rows if r.get("s3_file_key")})
    if file_keys:
        fmt = ", ".join(["'" + k.replace("'", "''") + "'" for k in file_keys])
        cur.execute(f"SELECT DISTINCT s3_file_key FROM {RAW_VETRIC_TABLE} WHERE s3_file_key IN ({fmt})")
        existing  = {row[0] for row in cur.fetchall()}
        to_delete = existing.intersection(set(file_keys))
        if to_delete:
            fmt2 = ", ".join(["'" + k.replace("'", "''") + "'" for k in to_delete])
            cur.execute(f"DELETE FROM {RAW_VETRIC_TABLE} WHERE s3_file_key IN ({fmt2})")
            logger.info(f"Deleted existing rows for {len(to_delete)} file(s) in raw vetric table")
            conn.commit()
    cur.close()

    now = datetime.now(timezone.utc).isoformat()
    records = []
    for r in rows:
        records.append({
            "RUN_ID":               r.get("run_id"),
            "ROW_ID":               r.get("row_id"),
            "S3_FILE_KEY":          r.get("s3_file_key"),
            "FILE_DATE":            r.get("file_date"),
            "LOADED_AT":            r.get("loaded_at"),
            "SOURCE":               r.get("source"),
            "INP_CRITERIA":         r.get("inp_criteria"),
            "INP_FULL_NAME":        r.get("inp_full_name"),
            "INP_FIRST_NAME":       r.get("inp_first_name"),
            "INP_LAST_NAME":        r.get("inp_last_name"),
            "INP_TITLE":            r.get("inp_title"),
            "INP_COMPANY":          r.get("inp_company"),
            "INP_LOCATION":         r.get("inp_location"),
            "INP_DOMAIN":           r.get("inp_domain"),
            "INP_LINKEDIN":         r.get("inp_linkedin"),
            "INP_COUNTRY":          r.get("inp_country"),
            "INP_LINKEDIN_SLUG":    r.get("inp_linkedin_slug"),
            "VETRIC_STATUS":        r.get("vetric_status"),
            "VETRIC_DATE":          r.get("vetric_date"),
            # VARIANT: pass as JSON string — Snowflake auto-parses via TRY_PARSE_JSON in SQL
            "VETRIC_RAW":           json.dumps(r.get("vetric_raw"), default=str) if r.get("vetric_raw") else None,
            "CREATED_AT":           now,
        })

    df = pd.DataFrame(records)
    success, n_chunks, n_rows, _ = write_pandas(
        conn, df, _TABLE,
        database=_DATABASE, schema=_SCHEMA,
        auto_create_table=False,
        overwrite=False,
        quote_identifiers=False,
    )
    if success:
        logger.info(f"Inserted {n_rows} rows into {RAW_VETRIC_TABLE} ({n_chunks} chunks)")
    else:
        raise RuntimeError(f"write_pandas failed for {RAW_VETRIC_TABLE}")
    return n_rows
