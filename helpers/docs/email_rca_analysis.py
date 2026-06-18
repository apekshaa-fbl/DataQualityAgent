"""
Company Email Data Quality — RCA Analysis
Tables: FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
        FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY
        FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB
"""
import os, sys
import snowflake.connector
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=True)
TOTP = sys.argv[1] if len(sys.argv) > 1 else None

params = dict(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "BI_TEAM"),
    database="FIRMOGRAPHICS",
    schema="ZEUS_BRONZE",
)
if TOTP:
    params["passcode"] = TOTP

print("Connecting to Snowflake...")
conn = snowflake.connector.connect(**params)
cur = conn.cursor()
print("Connected.\n")

def run(label, sql):
    print(f"  Running: {label}...")
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows

def table_md(cols, rows):
    if not rows:
        return "_No data returned._\n"
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    body   = "\n".join(
        "| " + " | ".join(str(v) if v is not None else "NULL" for v in row) + " |"
        for row in rows
    )
    return header + "\n" + sep + "\n" + body + "\n"

sections = []
run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ── 1. Overall email coverage by country ──────────────────────────────────────
cols, rows = run("1. Coverage by country", """
WITH company_email_counts AS (
  SELECT
    h.ID,
    COALESCE(NULLIF(TRIM(h.HQ_COUNTRY), ''), 'UNKNOWN') AS country,
    COUNT(e.EMAIL) AS email_count
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  LEFT JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID = e.ID
  WHERE h.STATUS = 'PUBLISHED'
  GROUP BY h.ID, COALESCE(NULLIF(TRIM(h.HQ_COUNTRY), ''), 'UNKNOWN')
)
SELECT
  country,
  COUNT(*)                                                              AS total_companies,
  SUM(CASE WHEN email_count >= 1 THEN 1 ELSE 0 END)                    AS with_email,
  SUM(CASE WHEN email_count = 0  THEN 1 ELSE 0 END)                    AS missing_email,
  ROUND(100.0 * SUM(CASE WHEN email_count >= 1 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2)                                       AS pct_with_email,
  ROUND(100.0 * SUM(CASE WHEN email_count = 0  THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2)                                       AS pct_missing
FROM company_email_counts
GROUP BY country
ORDER BY total_companies DESC
""")
sections.append(("1. Email Coverage by Country (PUBLISHED Companies)", cols, rows,
    "% of PUBLISHED companies with at least 1 email. `missing_email` = source team backfill target."))

# ── 2. PUBLISHED companies with FQDN but zero emails ─────────────────────────
cols2, rows2 = run("2. Has FQDN but no email", """
WITH base AS (
  SELECT
    h.ID,
    COALESCE(NULLIF(TRIM(h.HQ_COUNTRY), ''), 'UNKNOWN') AS country,
    COUNT(e.EMAIL) AS email_count
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  LEFT JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID = e.ID
  WHERE h.STATUS = 'PUBLISHED'
    AND h.FQDN IS NOT NULL AND TRIM(h.FQDN) <> ''
  GROUP BY h.ID, COALESCE(NULLIF(TRIM(h.HQ_COUNTRY), ''), 'UNKNOWN')
)
SELECT
  country,
  COUNT(*)                                                             AS companies_with_fqdn,
  SUM(CASE WHEN email_count = 0 THEN 1 ELSE 0 END)                    AS missing_email,
  SUM(CASE WHEN email_count >= 1 THEN 1 ELSE 0 END)                   AS has_email,
  ROUND(100.0 * SUM(CASE WHEN email_count = 0 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2)                                      AS pct_missing
FROM base
GROUP BY country
ORDER BY pct_missing DESC
""")
sections.append(("2. PUBLISHED Companies with FQDN but ZERO Emails", cols2, rows2,
    "Has a website domain but no company email. Primary source team backfill target."))

# ── 3. Email format validity ───────────────────────────────────────────────────
cols3, rows3 = run("3. Format validity", """
WITH classified AS (
  SELECT
    CASE
      WHEN EMAIL IS NULL OR TRIM(EMAIL) = ''        THEN 'empty'
      WHEN EMAIL NOT LIKE '%@%'                     THEN 'invalid_no_at'
      WHEN NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),
           '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$') THEN 'invalid_format'
      ELSE 'valid'
    END AS format_status
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
)
SELECT format_status, COUNT(*) AS email_rows,
       ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
FROM classified
GROUP BY format_status
ORDER BY email_rows DESC
""")
sections.append(("3. Email Format Validity", cols3, rows3,
    "`valid` = passes RFC regex. Invalid/empty must be hard-filtered before delivery."))

# ── 4. System / blocked email type breakdown ──────────────────────────────────
cols4, rows4 = run("4. Email type breakdown", """
WITH classified AS (
  SELECT
    CASE
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),
           '^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*')
        THEN 'system_blocked'
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),
           '^(admin|webmaster|hostmaster|root|support|info|hello|help|contact|sales|enquir|billing|accounts|hr|careers|jobs|marketing|press|media|legal|privacy|service|team|office|reception|general)@.*')
        THEN 'generic_role_based'
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),
           '@(gmail[.]com|yahoo[.]com|hotmail[.]com|outlook[.]com|icloud[.]com|live[.]com|aol[.]com|protonmail[.]com|mail[.]com)')
        THEN 'free_provider'
      ELSE 'specific_company'
    END AS email_type
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)), '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')
)
SELECT email_type, COUNT(*) AS count,
       ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
FROM classified
GROUP BY email_type
ORDER BY count DESC
""")
sections.append(("4. Email Type: System / Generic / Free / Specific", cols4, rows4,
    "`system_blocked` = must exclude. `free_provider` = exclude unless no company email. `generic_role_based` = acceptable but lower priority. `specific_company` = best."))

# ── 5. System emails by country ───────────────────────────────────────────────
cols5, rows5 = run("5. System emails by country", """
WITH base AS (
  SELECT
    COALESCE(NULLIF(TRIM(COUNTRY), ''), 'UNKNOWN') AS country,
    CASE WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),
         '^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*')
         THEN 1 ELSE 0 END AS is_system
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)), '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')
)
SELECT country,
  COUNT(*) AS total_emails,
  SUM(is_system) AS system_blocked,
  ROUND(100.0 * SUM(is_system) / NULLIF(COUNT(*), 0), 2) AS pct_system_blocked
FROM base
GROUP BY country
ORDER BY pct_system_blocked DESC
LIMIT 20
""")
sections.append(("5. System/Blocked Email Rate by Country (Top 20)", cols5, rows5,
    "Countries with highest % of system emails. Platform team filter target."))

# ── 6. Verification status distribution ───────────────────────────────────────
cols6, rows6 = run("6. Verification status", """
WITH totals AS (SELECT COUNT(*) AS n FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS)
SELECT
  COALESCE(NULLIF(TRIM(VERIFICATION_STATUS), ''), 'NULL/unverified') AS verification_status,
  COUNT(*) AS row_count,
  ROUND(COUNT(*)::NUMERIC / NULLIF(totals.n, 0) * 100, 2) AS pct
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS CROSS JOIN totals
GROUP BY COALESCE(NULLIF(TRIM(VERIFICATION_STATUS), ''), 'NULL/unverified'), totals.n
ORDER BY row_count DESC
""")
sections.append(("6. Verification Status Distribution", cols6, rows6,
    "Overall deliverability verification status. `NULL/unverified` = no check run yet — must go through Findymail → Million → BounceBan."))

# ── 7. Primary verifier x status breakdown ────────────────────────────────────
cols7, rows7 = run("7. Verifier breakdown", """
SELECT
  COALESCE(NULLIF(TRIM(PRIMARY_VERIFIER), ''), 'NULL') AS verifier,
  COALESCE(NULLIF(TRIM(PRIMARY_STATUS),   ''), 'NULL') AS status,
  COUNT(*) AS count,
  ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
GROUP BY COALESCE(NULLIF(TRIM(PRIMARY_VERIFIER), ''), 'NULL'),
         COALESCE(NULLIF(TRIM(PRIMARY_STATUS),   ''), 'NULL')
ORDER BY count DESC
LIMIT 30
""")
sections.append(("7. Primary Verifier x Status Breakdown", cols7, rows7,
    "Which verifier ran and what status it returned. Identifies unverified gaps per vendor."))

# ── 8. Domain mismatch by country ─────────────────────────────────────────────
cols8, rows8 = run("8. Domain mismatch", """
WITH parsed AS (
  SELECT
    COALESCE(NULLIF(TRIM(h.HQ_COUNTRY), ''), 'UNKNOWN') AS country,
    SPLIT_PART(LOWER(TRIM(h.FQDN)), '.', 1)                          AS company_root,
    SPLIT_PART(SPLIT_PART(LOWER(TRIM(e.EMAIL)), '@', 2), '.', 1)     AS email_root
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID = e.ID
  WHERE h.FQDN IS NOT NULL AND TRIM(h.FQDN) <> ''
    AND e.EMAIL IS NOT NULL AND e.EMAIL LIKE '%@%'
    AND h.FQDN LIKE '%.%'
)
SELECT
  country,
  COUNT(*) AS total_pairs,
  SUM(CASE WHEN company_root = email_root AND company_root <> '' THEN 1 ELSE 0 END) AS domain_match,
  SUM(CASE WHEN company_root <> email_root OR company_root = ''  THEN 1 ELSE 0 END) AS domain_mismatch,
  ROUND(100.0 * SUM(CASE WHEN company_root = email_root AND company_root <> '' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2) AS pct_match,
  ROUND(100.0 * SUM(CASE WHEN company_root <> email_root OR company_root = '' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2) AS pct_mismatch
FROM parsed
GROUP BY country
ORDER BY pct_mismatch DESC
LIMIT 20
""")
sections.append(("8. Email Domain vs Company FQDN Mismatch (Top 20 Countries)", cols8, rows8,
    "High mismatch = emails from unrelated/unverified domains. Platform team filter target."))

# ── 9. Companies with >5 emails ───────────────────────────────────────────────
cols9, rows9 = run("9. Excessive emails", """
WITH per_company AS (
  SELECT
    ID,
    COALESCE(NULLIF(TRIM(COUNTRY), ''), 'UNKNOWN') AS country,
    SUM(CASE WHEN EMAIL IS NOT NULL AND TRIM(EMAIL) <> '' THEN 1 ELSE 0 END) AS email_count
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  GROUP BY ID, COALESCE(NULLIF(TRIM(COUNTRY), ''), 'UNKNOWN')
),
rollup AS (
  SELECT country,
    COUNT(*) AS company_country_pairs,
    SUM(CASE WHEN email_count > 5 THEN 1 ELSE 0 END) AS gt5
  FROM per_company
  GROUP BY country
)
SELECT country, company_country_pairs,
       gt5 AS companies_with_gt5_emails,
       ROUND(100.0 * gt5 / NULLIF(company_country_pairs, 0), 2) AS pct_gt5
FROM rollup
ORDER BY pct_gt5 DESC
""")
sections.append(("9. Companies with >5 Emails per Country", cols9, rows9,
    "Business rule: max 5 best emails per company per country. Platform team trim target."))

# ── 10. Duplicate email summary ───────────────────────────────────────────────
cols10, rows10 = run("10. Duplicates", """
WITH counts AS (
  SELECT LOWER(TRIM(EMAIL)) AS email_clean, COUNT(*) AS occurrences
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)), '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')
  GROUP BY LOWER(TRIM(EMAIL))
)
SELECT
  COUNT(*) AS total_distinct_emails,
  SUM(CASE WHEN occurrences = 1 THEN 1 ELSE 0 END) AS unique_emails,
  SUM(CASE WHEN occurrences > 1 THEN 1 ELSE 0 END) AS duplicate_emails,
  ROUND(SUM(CASE WHEN occurrences > 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2) AS duplicate_pct
FROM counts
""")
sections.append(("10. Duplicate Email Summary", cols10, rows10,
    "Same cleaned email across multiple company records — indicates shared/generic addresses."))

# ── 11. ENABLED flag ──────────────────────────────────────────────────────────
cols11, rows11 = run("11. Enabled flag", """
SELECT
  COALESCE(ENABLED::VARCHAR, 'NULL') AS enabled,
  COUNT(*) AS count,
  ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
GROUP BY COALESCE(ENABLED::VARCHAR, 'NULL')
ORDER BY count DESC
""")
sections.append(("11. Email ENABLED Flag Distribution", cols11, rows11,
    "Disabled emails should not surface in product."))

# ── 12. Deliverability table summary ─────────────────────────────────────────
cols12, rows12 = run("12. Deliverability table", """
WITH totals AS (SELECT COUNT(*) AS n FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY)
SELECT
  COALESCE(NULLIF(TRIM(DELIVERABILITY), ''), 'NULL') AS deliverability,
  COUNT(*) AS count,
  ROUND(COUNT(*)::NUMERIC / NULLIF(totals.n, 0) * 100, 2) AS pct
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY CROSS JOIN totals
GROUP BY COALESCE(NULLIF(TRIM(DELIVERABILITY), ''), 'NULL'), totals.n
ORDER BY count DESC
""")
sections.append(("12. Deliverability Status (BRZ_COMP_EMAIL_DELIVERABILITY)", cols12, rows12,
    "Final deliverability gate. Only `valid/deliverable` should go live."))

cur.close()
conn.close()
print("\nAll queries complete. Building report...")

# ── Build markdown ─────────────────────────────────────────────────────────────
md = f"""# Company Email Data Quality — RCA Report

**Run date:** {run_date}
**Database:** `FIRMOGRAPHICS.ZEUS_BRONZE`
**Key tables:** `BRZ_COMP_EMAILS`, `BRZ_COMP_EMAIL_DELIVERABILITY`, `BRZ_COMPANY_HUB`
**Markets:** All (AU, NZ, MY, SG, HK, JP, ID, PH, US, CA + others in data)

---

## Executive Summary

This is the Quality team RCA deliverable per Suresh's request (2026-06-10).
Covers all 3 asks: **(1) RCA numbers across all markets, (2) what to disable/filter, (3) how to catch issues early.**

---

"""

for title, cols, rows, note in sections:
    md += f"## {title}\n\n"
    md += f"> {note}\n\n"
    md += table_md(cols, rows)
    md += "\n---\n\n"

md += """## Action Items by Owner

| # | Finding | Owner | Action |
|---|---------|-------|--------|
| 1 | PUBLISHED companies with FQDN but 0 emails (Section 2) | **Source team** | Backfill email discovery for these domains per country |
| 2 | Domain mismatch emails (Section 8) | **Platform team** | Filter: exclude emails where domain root ≠ company FQDN root |
| 3 | System/noreply emails in live data (Section 5) | **Platform team** | Add exclusion gate at publish: block noreply/donotreply/bounce patterns |
| 4 | Free provider emails (Section 4) | **Platform team** | Exclude gmail/yahoo/hotmail unless no company domain email exists |
| 5 | NULL verification_status (Section 6) | **Platform team** | Run through Findymail → Million → BounceBan waterfall before going live |
| 6 | Companies with >5 emails (Section 9) | **Platform team** | Trim to top 5 using priority rules below |
| 7 | Invalid format emails (Section 3) | **Platform team** | Hard filter: exclude non-RFC emails before any delivery |

---

## Quality Gate: Priority Rules for Top 5 Email Selection

```
1. Valid RFC email format
2. ENABLED = TRUE
3. Exclude system emails (noreply, donotreply, bounce, postmaster, mailer-daemon)
4. Exclude free email providers (gmail, yahoo, hotmail, outlook etc)
   → UNLESS no company domain email exists
5. Email domain root must match company FQDN root (with known exceptions)
6. Prefer deliverability = valid/deliverable > catch-all > unknown
7. Prefer specific emails over generic role-based (sales@, info@, contact@)
8. Cap at 5 emails per company per country
```

---

## Verifier Waterfall

| Priority | Vendor | Role |
|----------|--------|------|
| Primary | **Findymail** | First pass on all emails |
| Secondary | **Million Verifier** | If Findymail inconclusive/catchall |
| Tertiary | **BounceBan** | Final check on remaining unknowns |

Only confirmed **valid/deliverable** emails should go live.

---

## Early Detection (Prevent Recurrence)

| Check | Threshold | Action |
|-------|-----------|--------|
| Coverage drop per country | < 40% companies with email | Alert Quality team |
| System email rate | > 2% | Block release |
| Domain mismatch rate | > 20% | Flag for review |
| Unverified email rate (NULL) | > 30% | Trigger verifier batch run |
| Companies with >5 emails | > 5% per country | Trigger trim job |

Run on every release as part of the QMS pipeline.
"""

out_path = "/Users/apekshaa/Desktop/Data_Quality_Agents/docs/email_rca_report.md"
with open(out_path, "w") as f:
    f.write(md)

print(f"Report written to: {out_path}")
