"""
Reprocess CTA_monitoring only — reads from CTA_staging (already populated).
Much faster than full reprocess.

Usage:
    python3 run_monitoring_only.py --totp 123456
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--totp", default=None)
    args = parser.parse_args()

    totp = args.totp or input("Enter Snowflake TOTP: ").strip()

    from src.snowflake_conn import get_connection
    conn = get_connection(totp)
    print("Connected")

    from src.cta_summary import init_summary_tables, run_cta_monitoring
    from config import CTA_STAGING_TABLE

    init_summary_tables(conn)

    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT run_date FROM {CTA_STAGING_TABLE} ORDER BY run_date")
    run_dates = [str(row[0]) for row in cur.fetchall()]
    cur.close()

    print(f"Found {len(run_dates)} dates in staging\n")

    for run_date in run_dates:
        run_cta_monitoring(conn, run_date)
        print(f"  {run_date} done")

    conn.close()
    print(f"\nDone — {len(run_dates)} dates processed.")

if __name__ == "__main__":
    main()
