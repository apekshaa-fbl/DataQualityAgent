"""
People Pipeline — Configuration
All constants in one place. Do not hardcode values elsewhere.
"""
import re

# ── Snowflake ────────────────────────────────────────────────────────────────
RAW_TABLE        = "BI.RAW.dqms_ppl_raw_data"
RAW_VETRIC_TABLE = "BI.RAW.dqms_ppl_inp_with_vetric"

# ── S3 — Input CSVs ──────────────────────────────────────────────────────────
S3_INPUT_BUCKET = "fi-firmographics"
S3_INPUT_PREFIX = "data_quality/quality_monitoring/people/input/"

# ── S3 — Vetric cache (output) ────────────────────────────────────────────────
S3_VETRIC_BUCKET = "source-partners"
S3_VETRIC_PREFIX = "VTRC/2026/people/"

# ── Vetric API ────────────────────────────────────────────────────────────────
VETRIC_API_BASE = "https://api.vetric.io/linkedin/v1/profile"

# ── Input CSV columns → internal keys ────────────────────────────────────────
COLUMN_MAP = {
    "full name":       "inp_full_name",
    "first name":      "inp_first_name",
    "last name":       "inp_last_name",
    "title":           "inp_title",
    "company name":    "inp_company",
    "location":        "inp_location",
    "domain":          "inp_domain",
    "person linkedin": "inp_linkedin",
    "country code":    "inp_country",
    "criteria":        "inp_criteria",
    "competitor":      "source",
    "source":          "source",
    "data source":     "source",
    "provider":        "source",
    "competitor name": "source",
}


def normalise_slug(raw: str) -> str:
    """
    Normalise a LinkedIn profile URL or slug to a plain slug.
    e.g. 'https://www.linkedin.com/in/john-doe/' → 'john-doe'
         'linkedin.com/in/john-doe'              → 'john-doe'
         'john-doe'                              → 'john-doe'
    """
    if not raw:
        return ""
    s = str(raw).strip().lower()
    m = re.search(r"linkedin\.com/in/([^/?#\s]+)", s)
    if m:
        return m.group(1).rstrip("/")
    return ""


def make_run_id(file_date: str) -> str:
    """Build run_id in FYY.MM.DD format from a YYYY-MM-DD date string."""
    try:
        parts = file_date.split("-")
        yy, mm, dd = parts[0][2:], parts[1], parts[2]
        return f"F{yy}.{mm}.{dd}"
    except Exception:
        return f"F{file_date}"


def extract_date_from_filename(filename: str):
    """
    Extract date from filename.
    Supports YYYY-MM-DD and MM_DD_YY (e.g. dq_people_04_24_26.csv → 2026-04-24).
    """
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return m.group(1)
    m = re.search(r"_(\d{2})_(\d{2})_(\d{2})", filename)
    if m:
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        return f"20{yy}-{mm}-{dd}"
    return None
