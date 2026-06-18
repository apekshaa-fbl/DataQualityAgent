"""
CTA S3 Loader
Reads MM_DD_CTA.csv from s3://fi-firmographics/data_quality/trial_audits/2026/
All customers included — no SUB_STATUS filter.
Domain is cleaned but rows with no valid domain are kept (domain = None).
"""
import csv
import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from typing import List

import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)
from config import S3_CTA_BUCKET, S3_CTA_PREFIX, clean_domain


def _s3():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("CTA_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("CTA_AWS_SECRET_ACCESS_KEY"),
    )

logger = logging.getLogger(__name__)


def _make_cta_id(domain: str, sub_created: str, stripe_customer_id: str) -> str:
    """Unique ID: MD5(domain + sub_created + stripe_customer_id)."""
    raw = f"{domain or ''}{sub_created or ''}{stripe_customer_id or ''}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _extract_date_from_cta_filename(filename: str) -> str | None:
    """
    Extract date from MM_DD_CTA.csv filename.
    e.g. '06_01_CTA.csv' -> '2026-06-01'
    Year is always 2026 (files live under the /2026/ prefix).
    """
    m = re.match(r"^(\d{2})_(\d{2})_CTA\.csv$", filename, re.IGNORECASE)
    if m:
        mm, dd = m.group(1), m.group(2)
        return f"2026-{mm}-{dd}"
    return None


def _extract_date_from_s3_key(key: str) -> str | None:
    """Extract date from full S3 key: .../2026/MM/MM_DD_CTA.csv -> 2026-MM-DD"""
    filename = key.split("/")[-1]
    return _extract_date_from_cta_filename(filename)


def _safe_int(val) -> int | None:
    try:
        return int(float(str(val).strip())) if str(val).strip() else None
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    try:
        return float(str(val).strip()) if str(val).strip() else None
    except (ValueError, TypeError):
        return None


def load_cta_file(bucket: str, key: str) -> List[dict]:
    """
    Load a single MM_DD_CTA.csv from S3.
    Returns all rows — all SUB_STATUS values included.
    Domain is cleaned; rows with no valid domain keep domain=None.
    """
    s3 = _s3()
    filename = key.split("/")[-1]
    file_date = _extract_date_from_cta_filename(filename)
    if not file_date:
        logger.warning(f"Cannot extract date from '{filename}' — skipping file.")
        return []

    loaded_at = datetime.now(timezone.utc).isoformat()

    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as e:
        logger.error(f"Failed to read s3://{bucket}/{key}: {e}")
        return []

    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = body.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        logger.error(f"Could not decode {key}")
        return []

    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        raw = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}

        domain_raw = raw.get("HUBSPOT_DOMAIN_LINK", "")
        domain     = clean_domain(domain_raw)  # None for HubSpot search URLs / blanks

        stripe_customer_id = raw.get("STRIPE_CUSTOMER_ID", "")
        sub_created        = raw.get("SUB_CREATED", "")
        cta_id             = _make_cta_id(domain, sub_created, stripe_customer_id)

        rows.append({
            "cta_id":                               cta_id,
            "run_date":                             file_date,
            "customer_domain_raw":                  domain_raw,
            "customer_domain":                      domain,          # None = invalid / missing
            "customer_name":                        raw.get("STRIPE_NAME"),
            "hubspot_name":                         raw.get("HUBSPOT_NAME"),
            "stripe_customer_id":                   stripe_customer_id,
            "hubspot_icp":                          raw.get("HUBSPOT_ICP"),
            "sub_status":                           raw.get("SUB_STATUS"),
            "product_name":                         raw.get("PRODUCT_NAME"),
            "sub_plan_name":                        raw.get("SUB_PLAN_NAME"),
            "sub_plan_interval":                    raw.get("SUB_PLAN_INTERVAL"),
            "sub_plan_amount_aud":                  _safe_float(raw.get("SUB_PLAN_AMOUNT_AUD")),
            "sub_created":                          sub_created,
            "stripe_billing_country":               raw.get("STRIPE_BILLING_COUNTRY"),
            "available_monthly_subscription_credits": _safe_int(raw.get("AVAILABLE_MONTHLY_SUBSCRIPTION_CREDITS")),
            "hubspot_sales_team_size":              _safe_int(raw.get("HUBSPOT_SALES_TEAM_SIZE")),
            "stripe_currency":                      raw.get("STRIPE_CURRENCY"),
            "seats":                                _safe_int(raw.get("SEATS")),
            "loaded_at":                            loaded_at,
            "s3_file_key":                          key,
        })

    logger.info(f"Loaded {len(rows)} rows from s3://{bucket}/{key}")
    return rows


def list_cta_files(bucket: str = S3_CTA_BUCKET, prefix: str = S3_CTA_PREFIX) -> List[str]:
    """List all MM_DD_CTA.csv keys under the S3 prefix."""
    s3 = _s3()
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith("_CTA.csv"):
                keys.append(k)
    return sorted(keys)
