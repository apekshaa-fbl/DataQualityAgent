"""
Supabase Upsert — atomic.social_payloads (shared)
Conflict key: (platform, handle, request_type, profile_type)
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

import pandas as pd
from supabase import ClientOptions, create_client

logger = logging.getLogger(__name__)

SCHEMA      = "atomic"
TABLE       = "social_payloads"
CHUNKSIZE   = 500
ON_CONFLICT = "platform,handle,request_type,profile_type"


def _get_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not set in environment")
    return create_client(url, key, ClientOptions(schema=SCHEMA))


def upsert_vetric_rows(rows: List[dict], profile_type: str, label: str = "") -> int:
    """
    Upsert Vetric results into atomic.social_payloads.
    Only 200 and 404 rows are upserted (409 duplicates are skipped).

    profile_type: "PERSON" for people pipeline, "COMPANY" for company pipeline
    """
    eligible = [r for r in rows if r.get("vetric_status") in ("200", "404")]
    if not eligible:
        logger.info(f"No eligible rows (200/404) to upsert to Supabase [{label}].")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    records = []
    for r in eligible:
        handle = r.get("vetric_linkedin_slug") or r.get("inp_linkedin_slug") or r.get("inp_linkedin")
        records.append({
            "platform":     "LN",
            "handle":       handle,
            "profile_type": profile_type,
            "request_type": "PROFILE",
            "priority":     "P3-LOW",
            "status":       "COMPLETED",
            "created_at":   now,
            "event_ran_at": r.get("vetric_date") or now,
            "firmable_id":  None,
            "profile_id":   _extract_id(r.get("vetric_raw")),
            "status_code":  int(r["vetric_status"]),
            "error":        None,
            "post_count":   _extract_post_count(r.get("vetric_raw")),
        })

    return _upsert(records, label)


def _extract_id(vetric_raw) -> str | None:
    if not vetric_raw:
        return None
    try:
        data = vetric_raw if isinstance(vetric_raw, dict) else json.loads(vetric_raw)
        return str(data.get("id")) if data.get("id") is not None else None
    except Exception:
        return None


def _extract_post_count(vetric_raw):
    if not vetric_raw:
        return None
    try:
        data = vetric_raw if isinstance(vetric_raw, dict) else json.loads(vetric_raw)
        val = data.get("post_count")
        return float(val) if val is not None else None
    except Exception:
        return None


def _upsert(records: List[Dict[str, Any]], label: str = "") -> int:
    client = _get_client()
    df = pd.DataFrame(records)

    for col in ("created_at", "event_ran_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    df = df.where(pd.notnull(df), other=None)
    df = df.replace({float("nan"): None})

    chunks = [df[i:i + CHUNKSIZE] for i in range(0, len(df), CHUNKSIZE)]
    failed = 0

    for i, chunk in enumerate(chunks):
        try:
            client.table(TABLE).upsert(
                chunk.to_dict(orient="records"),
                on_conflict=ON_CONFLICT,
                ignore_duplicates=True,
            ).execute()
            logger.info(f"Supabase [{label}] chunk {i + 1}/{len(chunks)} pushed ({len(chunk)} rows)")
        except Exception as e:
            failed += 1
            logger.error(f"Supabase [{label}] chunk {i + 1} failed: {e}")

    logger.info(f"Supabase [{label}] upsert complete — {len(chunks) - failed}/{len(chunks)} chunks succeeded")
    if failed:
        logger.warning(f"Supabase [{label}] {failed} chunks failed")
    return len(records)
