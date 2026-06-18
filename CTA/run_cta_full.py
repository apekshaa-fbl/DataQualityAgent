"""
CTA Full Pipeline

Given a local CSV file or S3, runs all stages:
  1. Upload to S3 (if local file given, split by date)
  2. Load each date's file into CTA_raw_input
  3. Firmable match  -> CTA_staging
  4. Summary         -> CTA_summary_by_status
  5. Monitoring      -> CTA_monitoring

Usage:
    python3 run_cta_full.py --file ~/Desktop/Master_Customers.csv --totp 123456
    python3 run_cta_full.py --totp 123456                          # process all S3 files
    python3 run_cta_full.py --totp 123456 --month 06              # single month from S3
    python3 run_cta_full.py --totp 123456 --date 2026-06-01       # single date from S3
"""
import argparse
import csv
import io
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_cta_full")


def _banner(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def get_existing_dates(conn) -> set:
    """Return set of run_dates already in CTA_raw_input."""
    from config import CTA_RAW_INPUT_TABLE
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT run_date FROM {CTA_RAW_INPUT_TABLE}")
    dates = {str(row[0]) for row in cur.fetchall()}
    cur.close()
    return dates


def upload_local_file(local_path: str, existing_dates: set = None) -> list[str]:
    """
    Split a master CSV by SUB_CREATED date (2026 only) and upload to S3.
    Returns list of S3 keys uploaded.
    """
    import boto3
    from config import S3_CTA_BUCKET, S3_CTA_PREFIX

    print(f"\n  Reading {local_path}...")
    groups = defaultdict(list)
    fieldnames = None

    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(local_path, newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    raw_date = row.get("SUB_CREATED", "")[:10]
                    if not raw_date.startswith("2026"):
                        continue
                    groups[raw_date].append(row)
            break
        except UnicodeDecodeError:
            continue

    if not groups:
        print("  No 2026 rows found in file.")
        return []

    # Skip dates already loaded
    if existing_dates:
        new_dates = {d for d in groups if d not in existing_dates}
        skipped = len(groups) - len(new_dates)
        if skipped:
            print(f"  Skipping {skipped} already-loaded dates")
        groups = {d: groups[d] for d in new_dates}

    if not groups:
        print("  No new dates to upload.")
        return []

    print(f"  Uploading {len(groups)} new dates | {sum(len(v) for v in groups.values())} rows")

    s3 = boto3.client("s3")
    uploaded_keys = []

    for date_str in sorted(groups):
        rows = groups[date_str]
        _, mm, dd = date_str.split("-")
        filename = f"{mm}_{dd}_CTA.csv"
        s3_key = f"{S3_CTA_PREFIX}{mm}/{filename}"

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        body = buf.getvalue().encode("utf-8")

        try:
            s3.put_object(Bucket=S3_CTA_BUCKET, Key=s3_key, Body=body, ContentType="text/csv")
            print(f"  [S3] s3://{S3_CTA_BUCKET}/{s3_key}  ({len(rows)} rows)")
            uploaded_keys.append(s3_key)
        except Exception as e:
            print(f"  [FAIL] {s3_key}: {e}")

    return uploaded_keys


def main():
    parser = argparse.ArgumentParser(description="CTA Full Pipeline")
    parser.add_argument("--file",  default=None, help="Local CSV file path (Master_Customers_*.csv)")
    parser.add_argument("--totp",  default=None, help="Snowflake TOTP MFA code")
    parser.add_argument("--month", default=None, help="Run only this month e.g. 06")
    parser.add_argument("--date",  default=None, help="Run only this date e.g. 2026-06-01")
    args = parser.parse_args()

    _banner("CTA FULL PIPELINE")

    totp = args.totp or input("\nEnter Snowflake TOTP: ").strip()

    print("\n  Connecting to Snowflake...")
    from src.snowflake_conn import get_connection
    conn = get_connection(totp)
    print("  Connected")

    from src.cta_s3_loader import list_cta_files, load_cta_file
    from src.cta_raw_table import write_cta_input
    from src.cta_staging import init_staging_table, run_cta_staging
    from src.cta_summary import init_summary_tables, run_cta_summary_by_status, run_cta_monitoring
    from config import S3_CTA_BUCKET

    # Initialise tables once
    init_staging_table(conn)
    init_summary_tables(conn)

    # Step 1 — upload local file to S3 if provided
    if args.file:
        local_path = os.path.expanduser(args.file)
        if not os.path.exists(local_path):
            print(f"  File not found: {local_path}")
            sys.exit(1)
        existing_dates = get_existing_dates(conn)
        all_keys = upload_local_file(local_path, existing_dates)
        if not all_keys:
            print("  Nothing uploaded. Exiting.")
            sys.exit(0)
    else:
        all_keys = list_cta_files()
        print(f"\n  Found {len(all_keys)} CTA files in S3")

        if args.date:
            _, mm, dd = args.date.split("-")
            all_keys = [k for k in all_keys if f"/{mm}/{mm}_{dd}_CTA.csv" in k]
        elif args.month:
            all_keys = [k for k in all_keys if f"/2026/{args.month}/" in k]

    if not all_keys:
        print("  No matching files. Exiting.")
        sys.exit(0)

    print(f"\n  Processing {len(all_keys)} files\n")

    total_inserted = 0
    dates_processed = 0

    for key in all_keys:
        filename = key.split("/")[-1]
        print(f"\n── {filename} ──────────────────────────────")

        rows = load_cta_file(S3_CTA_BUCKET, key)
        if not rows:
            print("  No rows — skipping")
            continue

        run_date = rows[0]["run_date"]
        print(f"  run_date : {run_date}  |  rows: {len(rows)}")

        n = write_cta_input(conn, rows)
        conn.commit()
        print(f"  raw_input         : {n} inserted")

        n_staged = run_cta_staging(conn, run_date)
        print(f"  staging           : {n_staged} rows")

        run_cta_summary_by_status(conn, run_date)
        print(f"  summary_by_status : done")

        run_cta_monitoring(conn, run_date)
        print(f"  monitoring        : done")

        total_inserted += n
        dates_processed += 1

    conn.close()

    _banner("Pipeline Complete")
    print(f"  Dates processed  : {dates_processed}")
    print(f"  Raw rows inserted: {total_inserted}")


if __name__ == "__main__":
    main()
