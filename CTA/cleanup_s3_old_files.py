"""
Remove old flat S3 files (data_quality/trial_audits/2026/MM_DD_CTA.csv)
Keep only month-wise files (data_quality/trial_audits/2026/MM/MM_DD_CTA.csv)

Usage:
    python3 cleanup_s3_old_files.py           # dry run — lists what would be deleted
    python3 cleanup_s3_old_files.py --delete  # actually deletes
"""
import argparse
import re
import sys

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

BUCKET = "fi-firmographics"
PREFIX = "data_quality/trial_audits/2026/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true",
                        help="Actually delete files (default is dry run)")
    args = parser.parse_args()

    s3 = boto3.client("s3")

    # List all objects under the 2026 prefix
    old_keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            # Old format: sits directly under /2026/ with no month subfolder
            # e.g. data_quality/trial_audits/2026/06_01_CTA.csv
            # New format: data_quality/trial_audits/2026/06/06_01_CTA.csv
            parts = key.replace(PREFIX, "").split("/")
            if len(parts) == 1 and re.match(r"^\d{2}_\d{2}_CTA\.csv$", filename, re.IGNORECASE):
                old_keys.append(key)

    if not old_keys:
        print("No old flat files found — nothing to do.")
        sys.exit(0)

    print(f"Found {len(old_keys)} old flat files:")
    for k in old_keys:
        print(f"  {k}")

    if not args.delete:
        print(f"\nDry run — pass --delete to actually remove these {len(old_keys)} files.")
        sys.exit(0)

    # Delete in batches of 1000 (S3 limit)
    print(f"\nDeleting {len(old_keys)} files...")
    batch_size = 1000
    deleted = 0
    for i in range(0, len(old_keys), batch_size):
        batch = [{"Key": k} for k in old_keys[i:i + batch_size]]
        resp = s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch})
        deleted += len(resp.get("Deleted", []))
        errors   = resp.get("Errors", [])
        if errors:
            for e in errors:
                print(f"  [ERROR] {e['Key']}: {e['Message']}")

    print(f"Done — {deleted} files deleted.")


if __name__ == "__main__":
    main()
