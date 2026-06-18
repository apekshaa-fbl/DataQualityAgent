"""
Customer Trial Audit Pipeline — Configuration
All constants in one place. Do not hardcode values elsewhere.
"""
import os
import re

# ── Snowflake tables ──────────────────────────────────────────────────────────
INPUT_TABLE          = "BI.DW.cust_trial_input"
FIRMABLE_MATCH_TABLE = "BI.DW.cust_trial_firmable_match"
VETRIC_TABLE         = "BI.DW.cust_trial_input_with_vetric"
FIELD_COVERAGE_TABLE = "BI.DW.cust_trial_field_coverage"
PEOPLE_TABLE         = "BI.DW.cust_trial_people_coverage"
LOCATION_TABLE       = "BI.DW.cust_trial_location_coverage"
GAP_SUMMARY_TABLE    = "BI.DW.cust_trial_gap_summary"
QUALITY_TABLE        = "BI.DW.cust_trial_quality_score"

# ── CTA pipeline tables ───────────────────────────────────────────────────────
CTA_RAW_INPUT_TABLE         = "BI.DW.CTA_raw_input"
CTA_STAGING_TABLE           = "BI.DW.CTA_staging"
CTA_SUMMARY_BY_STATUS_TABLE = "BI.DW.CTA_summary_by_status"
CTA_MONITORING_TABLE        = "BI.DW.CTA_monitoring"

# ── S3 — Input CSV ────────────────────────────────────────────────────────────
S3_INPUT_BUCKET = "fi-firmographics"
S3_INPUT_PREFIX = "data_quality/trial_audit/input/"

# ── S3 — CTA input files (MM_DD_CTA.csv per day) ─────────────────────────────
S3_CTA_BUCKET = "fi-firmographics"
S3_CTA_PREFIX = "data_quality/trial_audits/2026/"

# ── S3 — Vetric cache ─────────────────────────────────────────────────────────
S3_VETRIC_BUCKET = "source-partners"
S3_VETRIC_PREFIX = "companies/source/vetric/2026/trial/"

# ── Vetric API ────────────────────────────────────────────────────────────────
VETRIC_API_BASE = "https://api.vetric.io/linkedin/v1/company"

# ── SUB_STATUS filter ─────────────────────────────────────────────────────────
VALID_SUB_STATUSES = {"trialing", "trialing - pending cancellation", "active"}

# ── Firmable gold tables ───────────────────────────────────────────────────────
FBL_COMPANY_CORE     = "firmographics.zeus_gold.gld_company_core"
FBL_COMPANY_DOWNLOAD = "firmographics.zeus_gold.gld_company_download"
FBL_PEOPLE_SRCH      = "firmographics.zeus_gold.gld_people_srch"
FBL_COMPANY_REGION   = "firmographics.zeus_gold.gld_company_region"
FBL_PEOPLE_CORE      = "firmographics.dev_zeus_gold.gld_people_core"

# ── Markets in scope ──────────────────────────────────────────────────────────
MARKETS = ("AU", "NZ", "MY", "SG", "HK", "JP", "ID", "PH", "US", "CA")


def clean_domain(raw: str):
    """
    Clean a raw HUBSPOT_DOMAIN_LINK value to a bare domain.
    Returns None if the value is a HubSpot CRM URL, blank, or 'link missing'.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    low = raw.lower()
    # HubSpot CRM URLs — skip
    if "app.hubspot.com" in low:
        return None
    # Junk values
    if low in ("link missing", "(blank)", "n/a", "na", "none"):
        return None
    # Strip protocol
    raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
    # Strip www.
    raw = re.sub(r"^www\.", "", raw, flags=re.IGNORECASE)
    # Strip trailing slash and path
    raw = raw.split("/")[0].strip()
    if not raw:
        return None
    return raw.lower()


def normalise_linkedin_slug(raw: str) -> str:
    """
    Convert a LinkedIn company URL or slug to a bare slug.
    e.g. 'https://linkedin.com/company/atlassian/' -> 'atlassian'
    """
    if not raw:
        return ""
    s = raw.strip().lower()
    m = re.search(r"linkedin\.com/company/([^/?#\s]+)", s)
    if m:
        return m.group(1).rstrip("/")
    return s.rstrip("/")


def make_run_id(file_date: str) -> str:
    """Build run_id in TYY.MM.DD format from a YYYY-MM-DD string."""
    try:
        parts = file_date.split("-")
        yy, mm, dd = parts[0][2:], parts[1], parts[2]
        return f"T{yy}.{mm}.{dd}"
    except Exception:
        return f"T{file_date}"


def extract_date_from_filename(filename: str):
    """Extract YYYY-MM-DD date from filename like Master_Customers_2026-05-27.csv."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return m.group(1)
    return None
