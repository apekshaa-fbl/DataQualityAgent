"""
People Pipeline — Entry Point

Usage:
    python3 run.py --s3-path s3://fi-firmographics/data_quality/quality_monitoring/people/input/dq_people_05_18_26.csv
    python3 run.py --s3-path s3://... --totp 123456
    python3 run.py --s3-path s3://... --reset    # ignore saved state, start fresh

Pipeline stages (all automatic — no prompts):
    Step 1 — Load CSV from S3, write to BI.RAW.dqms_ppl_raw_data
    Step 2 — Call Vetric API (200 / 404 / 409 only — all others retried)
    Step 3 — Write BI.RAW.dqms_ppl_inp_with_vetric
    Step 4 — Run all Snowflake SQL (staging, changes, coverage, accuracy, views)
    Step 5 — Pipeline complete

If the pipeline crashes, progress is saved to state/{run_id}.json.
Re-running will resume from the last incomplete step.
Use --reset to ignore saved state and start fresh.
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run")

# ── Stage names ───────────────────────────────────────────────────────────────
STAGE_LOAD_S3          = "load_s3"
STAGE_WRITE_RAW        = "write_raw_table"
STAGE_VETRIC           = "vetric_hit"
STAGE_WRITE_VETRIC     = "write_vetric_table"
STAGE_SQL_STAGING      = "sql_staging"
STAGE_CHANGES_DDL      = "sql_changes_ddl"
STAGE_CHANGES_INSERT   = "sql_changes_insert"
STAGE_COVERAGE_DDL     = "sql_coverage_ddl"
STAGE_COVERAGE_INSERT  = "sql_coverage_insert"
STAGE_ACCURACY_DDL     = "sql_accuracy_ddl"
STAGE_ACCURACY_INSERT  = "sql_accuracy_insert"
STAGE_VIEW_DASHBOARD   = "sql_view_dashboard"
STAGE_VIEW_BY_COUNTRY  = "sql_view_by_country"
STAGE_VIEW_OVERALL     = "sql_view_overall"
STAGE_SUPABASE         = "supabase_upsert"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _banner(text: str) -> None:
    print("\n" + "═" * 60)
    print(f"  {text}")
    print("═" * 60)


def _parse_s3_path(s3_path: str):
    """Parse s3://bucket/key into (bucket, key)."""
    s3_path = s3_path.strip()
    if s3_path.startswith("s3://"):
        s3_path = s3_path[5:]
    bucket, _, key = s3_path.partition("/")
    return bucket, key


def run_auto(state, stage_name: str, label: str, fn, *args):
    """
    Run a stage automatically.
    - If already done: skip.
    - If crashes: save failed state and exit.
    """
    from src.checkpoint import is_done, mark_done, mark_failed
    if is_done(state, stage_name):
        print(f"  [SKIP] {label} — already completed")
        return
    print(f"\n  [RUN]  {label}...")
    try:
        fn(*args)
        mark_done(state, stage_name)
        print(f"  [DONE] {label} ✓")
    except Exception as e:
        mark_failed(state, stage_name, e)
        print(f"\n  [CRASH] {label} failed: {e}")
        print(f"  Progress saved to state/. Re-run to resume from this step.")
        sys.exit(1)


# ── Stage functions ───────────────────────────────────────────────────────────

def stage_load_s3(state, bucket, key):
    from src.s3_loader import load_input_file
    from src.checkpoint import update_stats
    from config import normalise_slug

    rows = load_input_file(bucket, key)
    if not rows:
        print("    No rows found in input file. Exiting.")
        sys.exit(0)

    # Mark duplicates — same normalised LinkedIn slug appearing more than once
    seen = {}
    for row in rows:
        slug = normalise_slug(row.get("inp_linkedin") or "")
        if not slug:
            continue
        if slug in seen:
            row["vetric_status"] = "409"
        else:
            seen[slug] = True

    no_slug = sum(1 for r in rows if not normalise_slug(r.get("inp_linkedin") or ""))
    dupes   = sum(1 for r in rows if r.get("vetric_status") == "409")
    print(f"    Rows loaded: {len(rows)}")
    print(f"    With slug: {len(rows) - no_slug}  |  No slug: {no_slug}  |  Duplicates: {dupes}")
    update_stats(state, rows_loaded=len(rows), rows_no_slug=no_slug, rows_duplicate=dupes)
    state["_rows"] = rows


def stage_write_raw(conn, state):
    from src.raw_table import write_raw
    rows = state["_rows"]
    n = write_raw(conn, rows)
    conn.commit()
    print(f"    {n} rows written to BI.RAW.dqms_ppl_raw_data")


def stage_vetric(state):
    from src.vetric_live import fill_all, retry_400s
    from src.checkpoint import update_stats

    rows   = state["_rows"]
    active = [r for r in rows if r.get("vetric_status") != "409"]
    print(f"    Calling Vetric for {len(active)} rows (skipping {len(rows) - len(active)} duplicates)...")
    fill_all(active)

    # Safety net — fill_all resolves all to 200 or 404 internally
    v400_initial = sum(1 for r in active if r.get("vetric_status") == "400")
    if v400_initial:
        print(f"    {v400_initial} unexpected 400s — retrying with escalating timeouts...")
        retry_400s(active)

    v200  = sum(1 for r in rows if r.get("vetric_status") == "200")
    v404  = sum(1 for r in rows if r.get("vetric_status") == "404")
    v409  = sum(1 for r in rows if r.get("vetric_status") == "409")
    other = sum(1 for r in rows if r.get("vetric_status") not in ("200", "404", "409"))
    print(f"    Vetric results — 200:{v200}  404:{v404}  409 (duplicate):{v409}")
    if other:
        print(f"    WARNING: {other} rows have unexpected status — check logs")
    update_stats(state, vetric_200=v200, vetric_404=v404)
    state["_rows"] = rows


def stage_write_vetric(conn, state):
    from src.raw_vetric_table import write_raw_vetric
    rows = state["_rows"]
    n = write_raw_vetric(conn, rows)
    conn.commit()
    print(f"    {n} rows written to BI.RAW.dqms_ppl_inp_with_vetric")


def stage_supabase(state):
    from src.supabase_upsert import upsert_people_vetric_rows
    rows = state["_rows"]
    n = upsert_people_vetric_rows(rows)
    print(f"    {n} rows upserted to Supabase atomic.social_payloads")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="People Pipeline")
    parser.add_argument("--s3-path", required=True,
                        help="S3 path to input CSV  e.g. s3://fi-firmographics/.../dq_people_05_18_26.csv")
    parser.add_argument("--totp",  default=None, help="Snowflake TOTP MFA code")
    parser.add_argument("--reset", action="store_true",
                        help="Ignore saved state and start from scratch")
    parser.add_argument("--service-account", action="store_true",
                        help="Use service account key pair (no TOTP) — for automated runs")
    args = parser.parse_args()

    _banner("PEOPLE PIPELINE")

    bucket, key = _parse_s3_path(args.s3_path)
    print(f"\n  File : s3://{bucket}/{key}")

    # ── TOTP (time-sensitive — collect before anything else) ──────────────────
    totp = None
    if not args.service_account:
        totp = args.totp
        if not totp:
            totp = input("\nEnter Snowflake TOTP: ").strip()

    # ── Derive run_id from filename ───────────────────────────────────────────
    from config import extract_date_from_filename, make_run_id
    filename  = key.split("/")[-1]
    file_date = extract_date_from_filename(filename)
    if not file_date:
        from datetime import date
        file_date = str(date.today())
    run_id = make_run_id(file_date)
    print(f"  Run ID: {run_id}")

    # ── Load or create checkpoint state ──────────────────────────────────────
    from src.checkpoint import load_state, create_state, clear_state
    if args.reset:
        clear_state(run_id)

    state = load_state(run_id)
    if state:
        print(f"\n  Resuming run {run_id}")
        print(f"  Completed so far : {state.get('completed', [])}")
    else:
        print(f"\n  Starting new run {run_id}")
        state = create_state(run_id, [file_date])

    # ── Connect to Snowflake ──────────────────────────────────────────────────
    print("\n  Connecting to Snowflake...")
    if args.service_account:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from shared.snowflake_service import get_service_connection
        conn = get_service_connection()
    else:
        from src.snowflake_conn import get_connection
        conn = get_connection(totp)
    print("  Connected ✓")

    from src.sql_steps import (
        run_sql_staging,
        run_changes_ddl, run_changes_insert,
        run_coverage_ddl, run_coverage_insert,
        run_accuracy_ddl, run_accuracy_insert,
        run_view_dashboard, run_view_by_country, run_view_overall,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Load CSV + write raw input table
    # ─────────────────────────────────────────────────────────────────────────
    _banner("Step 1 — Load & ingest input file")

    run_auto(state, STAGE_LOAD_S3,
             "Load input CSV from S3 + mark duplicates (409)",
             stage_load_s3, state, bucket, key)

    run_auto(state, STAGE_WRITE_RAW,
             "Write BI.RAW.dqms_ppl_raw_data",
             stage_write_raw, conn, state)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Vetric API (200 / 404 / 409 only)
    # ─────────────────────────────────────────────────────────────────────────
    _banner("Step 2 — Vetric API")

    run_auto(state, STAGE_VETRIC,
             "Call Vetric for each LinkedIn slug",
             stage_vetric, state)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Write with-Vetric table
    # ─────────────────────────────────────────────────────────────────────────
    _banner("Step 3 — Write Vetric results to Snowflake")

    run_auto(state, STAGE_WRITE_VETRIC,
             "Write BI.RAW.dqms_ppl_inp_with_vetric",
             stage_write_vetric, conn, state)

    run_auto(state, STAGE_SUPABASE,
             "Upsert to Supabase atomic.social_payloads",
             stage_supabase, state)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — All Snowflake SQL
    # ─────────────────────────────────────────────────────────────────────────
    _banner("Step 4 — Run Snowflake SQL")

    run_auto(state, STAGE_SQL_STAGING,
             "CREATE staging table (match + score)",
             run_sql_staging, conn)

    run_auto(state, STAGE_CHANGES_DDL,
             "CREATE changes table (if not exists)",
             run_changes_ddl, conn)

    run_auto(state, STAGE_CHANGES_INSERT,
             "INSERT quality changes (0 rows on first run)",
             run_changes_insert, conn)

    run_auto(state, STAGE_COVERAGE_DDL,
             "CREATE coverage monitor table",
             run_coverage_ddl, conn)

    run_auto(state, STAGE_COVERAGE_INSERT,
             "INSERT coverage monitor rows",
             run_coverage_insert, conn)

    run_auto(state, STAGE_ACCURACY_DDL,
             "CREATE accuracy checks table",
             run_accuracy_ddl, conn)

    run_auto(state, STAGE_ACCURACY_INSERT,
             "INSERT accuracy check rows",
             run_accuracy_insert, conn)

    run_auto(state, STAGE_VIEW_DASHBOARD,
             "CREATE OR REPLACE VIEW dqms_ppl_dashboard_v",
             run_view_dashboard, conn)

    run_auto(state, STAGE_VIEW_BY_COUNTRY,
             "CREATE OR REPLACE VIEW dqms_ppl_overall_run_by_country",
             run_view_by_country, conn)

    run_auto(state, STAGE_VIEW_OVERALL,
             "CREATE OR REPLACE VIEW dqms_ppl_overall_run",
             run_view_overall, conn)

    conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — Done
    # ─────────────────────────────────────────────────────────────────────────
    _banner("Step 5 — Pipeline Complete")
    print(f"  Run ID      : {run_id}")
    print(f"  Rows loaded : {state.get('rows_loaded', '—')}")
    print(f"  No slug     : {state.get('rows_no_slug', '—')}")
    print(f"  Vetric 200  : {state.get('vetric_200', '—')}")
    print(f"  Vetric 404  : {state.get('vetric_404', '—')}")
    print(f"  Steps done  : {len(state.get('completed', []))}")
    print()


if __name__ == "__main__":
    main()
