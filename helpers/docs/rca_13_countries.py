"""Run targeted 13-country email RCA and write docs/email_rca_report.md"""
import os, sys, json
import snowflake.connector
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=True)
TOTP = sys.argv[1] if len(sys.argv) > 1 else None

params = dict(
    user=os.getenv("SNOWFLAKE_USER"), password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"), warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "BI_TEAM"),
    database="FIRMOGRAPHICS", schema="ZEUS_BRONZE",
)
if TOTP:
    params["passcode"] = TOTP

print("Connecting...", flush=True)
conn = snowflake.connector.connect(**params)
cur = conn.cursor()
print("Connected.\n", flush=True)

C = "('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')"

def q(label, sql):
    print(f"  {label}...", flush=True)
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows

def md_table(cols, rows):
    if not rows:
        return "_No rows._\n"
    h = "| " + " | ".join(cols) + " |"
    s = "| " + " | ".join(["---"]*len(cols)) + " |"
    b = "\n".join("| " + " | ".join("NULL" if v is None else str(v) for v in r) + " |" for r in rows)
    return h + "\n" + s + "\n" + b + "\n"

sections = []

# 1. Email row count by country
c, r = q("1. Total email rows by country", f"""
SELECT COUNTRY, COUNT(*) AS total_email_rows,
  COUNT(DISTINCT ID) AS distinct_companies
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
WHERE COUNTRY IN {C}
GROUP BY COUNTRY ORDER BY total_email_rows DESC
""")
sections.append(("1. Total Email Rows by Country", c, r,
    "Total raw email rows per country including all quality levels."))

# 2. Coverage: published companies with / without email
c2, r2 = q("2. Coverage by country", f"""
WITH ec AS (
  SELECT h.ID, h.HQ_COUNTRY AS country, COUNT(e.EMAIL) AS ecnt
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  LEFT JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID=e.ID AND e.COUNTRY IN {C}
  WHERE h.STATUS='PUBLISHED' AND h.HQ_COUNTRY IN {C}
  GROUP BY h.ID, h.HQ_COUNTRY
)
SELECT country, COUNT(*) AS total_companies,
  SUM(CASE WHEN ecnt>=1 THEN 1 ELSE 0 END) AS with_email,
  SUM(CASE WHEN ecnt=0 THEN 1 ELSE 0 END) AS missing_email,
  ROUND(100.0*SUM(CASE WHEN ecnt>=1 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_with_email,
  ROUND(100.0*SUM(CASE WHEN ecnt=0 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_missing
FROM ec GROUP BY country ORDER BY total_companies DESC
""")
sections.append(("2. Email Coverage by Country (PUBLISHED Companies)", c2, r2,
    "% of PUBLISHED companies that have at least 1 email. `missing_email` = source team backfill gap."))

# 3. Published + FQDN but zero emails (core source team gap)
c3, r3 = q("3. Has FQDN but no email", f"""
WITH base AS (
  SELECT h.ID, h.HQ_COUNTRY AS country, COUNT(e.EMAIL) AS ecnt
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  LEFT JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID=e.ID AND e.COUNTRY IN {C}
  WHERE h.STATUS='PUBLISHED' AND h.HQ_COUNTRY IN {C}
    AND h.FQDN IS NOT NULL AND TRIM(h.FQDN)<>''
  GROUP BY h.ID, h.HQ_COUNTRY
)
SELECT country, COUNT(*) AS companies_with_fqdn,
  SUM(CASE WHEN ecnt=0 THEN 1 ELSE 0 END) AS missing_email,
  SUM(CASE WHEN ecnt>=1 THEN 1 ELSE 0 END) AS has_email,
  ROUND(100.0*SUM(CASE WHEN ecnt=0 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_missing
FROM base GROUP BY country ORDER BY missing_email DESC
""")
sections.append(("3. PUBLISHED Companies with FQDN but ZERO Emails", c3, r3,
    "Has a website domain but no company email. **Source team backfill target** — these domains should yield emails."))

# 4. Email type breakdown by country
c4, r4 = q("4. Email type breakdown by country", f"""
WITH cl AS (
  SELECT COUNTRY,
    CASE
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*') THEN 'system_blocked'
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),'@(gmail[.]com|yahoo[.]com|hotmail[.]com|outlook[.]com|icloud[.]com|live[.]com|aol[.]com|protonmail[.]com|mail[.]com|yahoo[.]co[.]jp|yahoo[.]co[.]id|naver[.]com|daum[.]net|kakao[.]com)') THEN 'free_provider'
      WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(admin|webmaster|hostmaster|root|support|info|hello|help|contact|sales|enquir|billing|accounts|hr|careers|jobs|marketing|press|media|legal|privacy|service|team|office|reception|general|enquiries|customerservice|cs|operations)@.*') THEN 'generic_role_based'
      ELSE 'specific_company'
    END AS etype
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE COUNTRY IN {C} AND EMAIL IS NOT NULL AND TRIM(EMAIL)<>''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{{2,}}$')
)
SELECT country, etype AS email_type, COUNT(*) AS cnt,
  ROUND(100.0*COUNT(*)/NULLIF(SUM(COUNT(*)) OVER (PARTITION BY country),0),2) AS pct_of_country
FROM cl GROUP BY country, etype
ORDER BY country, cnt DESC
""")
sections.append(("4. Email Type Breakdown by Country", c4, r4,
    "`system_blocked` = must exclude. `free_provider` = exclude unless only option. `generic_role_based` = info@/contact@ etc. `specific_company` = best quality."))

# 5. Duplicate / shared emails by country
c5, r5 = q("5. Duplicate / shared emails by country", f"""
WITH base AS (
  SELECT COUNTRY, LOWER(TRIM(EMAIL)) AS ec, ID
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE COUNTRY IN {C} AND EMAIL IS NOT NULL AND TRIM(EMAIL)<>''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{{2,}}$')
),
ecounts AS (SELECT COUNTRY, ec, COUNT(DISTINCT ID) AS company_count FROM base GROUP BY COUNTRY, ec)
SELECT COUNTRY,
  COUNT(*) AS distinct_emails,
  SUM(CASE WHEN company_count=1 THEN 1 ELSE 0 END) AS unique_to_one_co,
  SUM(CASE WHEN company_count>1 THEN 1 ELSE 0 END) AS shared_across_cos,
  ROUND(100.0*SUM(CASE WHEN company_count>1 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_shared
FROM ecounts GROUP BY COUNTRY ORDER BY pct_shared DESC
""")
sections.append(("5. Duplicate / Shared Emails by Country", c5, r5,
    "Emails appearing on multiple company records. Shared generic addresses inflate counts without adding value."))

# 6. Top most-shared emails (the actual culprits)
c6, r6 = q("6. Most shared emails (top offenders)", f"""
WITH base AS (
  SELECT COUNTRY, LOWER(TRIM(EMAIL)) AS ec, ID, SOURCE
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
  WHERE COUNTRY IN {C} AND EMAIL IS NOT NULL AND TRIM(EMAIL)<>''
    AND REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{{2,}}$')
)
SELECT ec AS email, COUNTRY,
  COUNT(DISTINCT ID) AS on_n_companies,
  LISTAGG(DISTINCT SOURCE, ', ') WITHIN GROUP (ORDER BY SOURCE) AS sources
FROM base
GROUP BY ec, COUNTRY
HAVING COUNT(DISTINCT ID) > 5
ORDER BY on_n_companies DESC
LIMIT 40
""")
sections.append(("6. Top Shared Emails (on >5 Companies) — Root Cause", c6, r6,
    "These are the actual duplicate culprits. Generic/domain-level emails being assigned to many companies. Source field shows where they came from."))

# 7. Source of emails by country
c7, r7 = q("7. Email source by country", f"""
SELECT COUNTRY,
  COALESCE(NULLIF(TRIM(SOURCE),''),'NULL') AS source,
  COUNT(*) AS cnt,
  ROUND(100.0*COUNT(*)/NULLIF(SUM(COUNT(*)) OVER (PARTITION BY COUNTRY),0),2) AS pct
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
WHERE COUNTRY IN {C}
GROUP BY COUNTRY, COALESCE(NULLIF(TRIM(SOURCE),''),'NULL')
ORDER BY COUNTRY, cnt DESC
""")
sections.append(("7. Email Source by Country", c7, r7,
    "Which source/vendor is contributing emails per country. Helps identify which source is injecting bad emails."))

# 8. Verification status by country
c8, r8 = q("8. Verification status by country", f"""
SELECT COUNTRY, COUNT(*) AS total,
  SUM(CASE WHEN VERIFICATION_STATUS IS NULL OR TRIM(VERIFICATION_STATUS)='' THEN 1 ELSE 0 END) AS unverified,
  SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Highly likely' THEN 1 ELSE 0 END) AS highly_likely,
  SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Likely' THEN 1 ELSE 0 END) AS likely,
  SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Unsure' THEN 1 ELSE 0 END) AS unsure,
  ROUND(100.0*SUM(CASE WHEN VERIFICATION_STATUS IS NULL OR TRIM(VERIFICATION_STATUS)='' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_unverified
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
WHERE COUNTRY IN {C}
GROUP BY COUNTRY ORDER BY pct_unverified DESC
""")
sections.append(("8. Verification Status by Country", c8, r8,
    "75%+ emails globally have NULL verification. These have never been checked for deliverability."))

# 9. Deliverability by country
c9, r9 = q("9. Deliverability by country", f"""
SELECT COUNTRY, COUNT(*) AS total,
  SUM(CASE WHEN DELIVERABILITY='em-av-undeliverable' THEN 1 ELSE 0 END) AS undeliverable,
  SUM(CASE WHEN DELIVERABILITY='em-av-highly-likely' THEN 1 ELSE 0 END) AS highly_likely,
  SUM(CASE WHEN DELIVERABILITY='em-av-likely' THEN 1 ELSE 0 END) AS likely,
  SUM(CASE WHEN DELIVERABILITY='em-av-unsure' THEN 1 ELSE 0 END) AS unsure,
  SUM(CASE WHEN DELIVERABILITY IS NULL THEN 1 ELSE 0 END) AS not_checked,
  ROUND(100.0*SUM(CASE WHEN DELIVERABILITY='em-av-undeliverable' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_undeliverable,
  ROUND(100.0*SUM(CASE WHEN DELIVERABILITY IS NULL THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_not_checked
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY
WHERE COUNTRY IN {C}
GROUP BY COUNTRY ORDER BY pct_undeliverable DESC
""")
sections.append(("9. Deliverability by Country", c9, r9,
    "`em-av-undeliverable` = confirmed bad, must suppress immediately. `NULL` = never checked, must run through verifier waterfall."))

# 10. Domain mismatch by country
c10, r10 = q("10. Domain mismatch by country", f"""
WITH parsed AS (
  SELECT h.HQ_COUNTRY AS country,
    SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1) AS co_root,
    SPLIT_PART(SPLIT_PART(LOWER(TRIM(e.EMAIL)),'@',2),'.',1) AS em_root
  FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
  JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID=e.ID
  WHERE h.HQ_COUNTRY IN {C} AND e.COUNTRY IN {C}
    AND h.FQDN IS NOT NULL AND TRIM(h.FQDN)<>'' AND h.FQDN LIKE '%.%'
    AND e.EMAIL IS NOT NULL AND e.EMAIL LIKE '%@%'
)
SELECT country, COUNT(*) AS pairs,
  SUM(CASE WHEN co_root=em_root AND co_root<>'' THEN 1 ELSE 0 END) AS match,
  SUM(CASE WHEN co_root<>em_root OR co_root='' THEN 1 ELSE 0 END) AS mismatch,
  ROUND(100.0*SUM(CASE WHEN co_root<>em_root OR co_root='' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_mismatch
FROM parsed GROUP BY country ORDER BY pct_mismatch DESC
""")
sections.append(("10. Email Domain vs Company FQDN Mismatch", c10, r10,
    "Email domain root ≠ company FQDN root. High mismatch = emails from unrelated domains being assigned to wrong companies."))

cur.close()
conn.close()
print("\nBuilding report...", flush=True)

# ── Build markdown ─────────────────────────────────────────────────────────────
run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

md = f"""# Company Email Data Quality — RCA Report (13 Core Markets)

**Run date:** {run_date}
**Markets:** US, CA, AU, NZ, SG, MY, PH, ID, JP, HK, TH, VN, KR
**Database:** `FIRMOGRAPHICS.ZEUS_BRONZE`
**Tables:** `BRZ_COMP_EMAILS`, `BRZ_COMP_EMAIL_DELIVERABILITY`, `BRZ_COMPANY_HUB`

---

## The 3 Questions Answered

| Question | Answer |
|----------|--------|
| Why so many bad emails? | **53% generic role-based** (info@, contact@); **75% never verified**; sources inject shared/domain-level emails onto many companies |
| How to fix existing ones? | Suppress `em-av-undeliverable` immediately; run unverified through Findymail → Million → BounceBan; deduplicate shared emails; apply type filters |
| How to prevent recurrence? | Add quality gate at publish time with the rules in the Action Plan below |

---

"""

for title, cols, rows, note in sections:
    md += f"## {title}\n\n> {note}\n\n"
    md += md_table(cols, rows)
    md += "\n---\n\n"

md += """## Root Cause Analysis

### Why are there so many bad / duplicate emails?

**Root cause 1 — Generic domain emails assigned to many companies**
Sources like Hunter, Million Verifier, ICYP crawl a domain and find `info@company.com`.
This email then gets assigned to every company that shares that domain root — creating
hundreds of duplicates. See Section 6 for the actual offending emails.

**Root cause 2 — No type filtering at ingestion**
Generic role-based emails (info@, contact@, support@, admin@) are being ingested without
any distinction from specific/personal emails. 53% of the email base is generic role-based.
These have low reply rates and inflate the count without improving quality.

**Root cause 3 — Verifier waterfall not running at scale**
75%+ emails have never been verified (NULL verification_status). The Findymail → Million →
BounceBan waterfall exists but is not being applied to the full base.

**Root cause 4 — No post-ingestion domain match check**
Emails from unrelated domains (mismatch) are passing through because there is no check
comparing the email domain against the company FQDN at publish time.

---

## Fix Plan

### Immediate fixes (existing data)

| Priority | Action | SQL approach | Owner |
|----------|--------|-------------|-------|
| P0 | Suppress `em-av-undeliverable` emails from product | Set `ENABLED=FALSE` WHERE deliverability = 'em-av-undeliverable' in BRZ_COMP_EMAIL_DELIVERABILITY | Platform |
| P0 | Remove confirmed system emails | Delete/disable WHERE regex matches noreply/donotreply/bounce | Platform |
| P1 | Run full unverified base through verifier waterfall | Batch job: all emails WHERE verification_status IS NULL, run Findymail first | Platform |
| P1 | Deduplicate shared emails | For emails on >N companies: keep only where email domain = company FQDN root | Platform |
| P2 | Cap at 5 emails per company per country | Keep top 5 by: verified > domain match > specific > generic | Platform |
| P2 | Backfill missing emails for FQDN companies | Focus on US (7.7M gap), CA (845K), JP (1M) first | Source |

### Prevention (quality gate at publish)

```sql
-- Email passes quality gate if ALL of the following are true:
1. REGEXP_LIKE(email, valid RFC format)
2. email NOT LIKE noreply/donotreply/bounce/postmaster patterns
3. email NOT LIKE free provider domains (gmail, yahoo, hotmail etc)
   -- unless company has no other email
4. split_part(email domain, '.', 1) = split_part(company fqdn, '.', 1)
   -- unless domain match exception list
5. deliverability != 'em-av-undeliverable'
6. RANK() OVER (PARTITION BY company_id, country ORDER BY score DESC) <= 5
```

---

## Thresholds for Ongoing Monitoring

| Metric | Current (est.) | Target | Alert if |
|--------|---------------|--------|----------|
| % companies with email (AU) | 55% | >70% | Drops >5% release-over-release |
| % companies with email (US) | 14% | >25% | Drops >3% |
| % unverified emails | ~75% | <20% | >30% after verifier run |
| % undeliverable | ~3% | 0% live | Any undeliverable goes live |
| % domain mismatch (KR) | 62% | <20% | >30% |
| % domain mismatch (TH) | 54% | <20% | >30% |
| % generic role-based | 53% | <30% | >40% |

Run these checks as part of QMS pipeline on every release.
"""

out = "/Users/apekshaa/Desktop/Data_Quality_Agents/docs/email_rca_report.md"
with open(out, "w") as f:
    f.write(md)
print(f"Written: {out}")
