"""
CTA Reprocess — Stages 3-5 only (staging, summary, monitoring).
Reads existing run_dates from CTA_raw_input, skips S3 and raw insert.

Usage:
    python3 run_cta_reprocess.py --totp 123456
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_cta_reprocess")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--totp", default=None)
    args = parser.parse_args()

    totp = args.totp or input("Enter Snowflake TOTP: ").strip()

    from src.snowflake_conn import get_connection
    conn = get_connection(totp)
    print("Connected to Snowflake")

    from src.cta_staging import init_staging_table, run_cta_staging
    from src.cta_summary import init_summary_tables, run_cta_summary_by_status, run_cta_monitoring
    from config import CTA_RAW_INPUT_TABLE

    init_staging_table(conn)
    init_summary_tables(conn)

    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT run_date FROM {CTA_RAW_INPUT_TABLE} ORDER BY run_date")
    run_dates = [str(row[0]) for row in cur.fetchall()]
    cur.close()

    print(f"\nFound {len(run_dates)} run_dates to process\n")

    for run_date in run_dates:
        print(f"── {run_date} ──────────────────────────────")
        n = run_cta_staging(conn, run_date)
        print(f"  staging    : {n} rows")
        run_cta_summary_by_status(conn, run_date)
        print(f"  summary_by_status : done")
        run_cta_monitoring(conn, run_date)
        print(f"  monitoring : done")

    conn.close()
    print(f"\nDone — {len(run_dates)} dates processed.")


if __name__ == "__main__":
    main()
