"""
Split master CSV by SUB_CREATED date (2026 only) and upload to S3.

Output path: s3://fi-firmographics/data_quality/trial_audits/2026/MM_DD_CTA.csv

Usage:
    cd Customer_Trial_Audits
    python3 upload_to_s3.py
"""
import csv
import io
import os
import sys
from collections import defaultdict

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

SOURCE_FILE = "/Users/apekshaa/Downloads/Master_Customers_1781668122137.csv"
S3_BUCKET   = "fi-firmographics"
S3_PREFIX   = "data_quality/trial_audits/2026/"


def main():
    # ── Read and group by date ────────────────────────────────────────────────
    groups = defaultdict(list)
    fieldnames = None

    with open(SOURCE_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            raw_date = row.get("SUB_CREATED", "")[:10]  # YYYY-MM-DD
            if not raw_date.startswith("2026"):
                continue
            groups[raw_date].append(row)

    if not groups:
        print("No 2026 rows found. Exiting.")
        sys.exit(0)

    print(f"Found {len(groups)} unique 2026 dates | "
          f"{sum(len(v) for v in groups.values())} total rows")

    # ── Upload one file per date ──────────────────────────────────────────────
    s3 = boto3.client("s3")
    uploaded = 0
    skipped  = 0

    for date_str in sorted(groups):
        rows = groups[date_str]
        _, mm, dd = date_str.split("-")
        filename = f"{mm}_{dd}_CTA.csv"
        s3_key   = f"{S3_PREFIX}{mm}/{filename}"   # month subfolder

        # Write CSV to in-memory buffer
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        body = buf.getvalue().encode("utf-8")

        try:
            s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=body, ContentType="text/csv")
            print(f"  [OK] s3://{S3_BUCKET}/{s3_key}  ({len(rows)} rows)")
            uploaded += 1
        except Exception as e:
            print(f"  [FAIL] {s3_key}: {e}")
            skipped += 1

    print(f"\nDone — {uploaded} files uploaded, {skipped} failed.")


if __name__ == "__main__":
    main()
