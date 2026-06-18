# Email Data Quality — QuickSight Dashboard Setup

**Owner:** Quality team
**Markets:** US, CA, AU, NZ, SG, MY, PH, ID, JP, HK, TH, VN, KR
**Refresh:** Weekly — Friday 6 PM IST via Snowflake Task
**Source:** `FIRMOGRAPHICS.ZEUS_BRONZE`

---

## Overview

```
FIRMOGRAPHICS.ZEUS_BRONZE  (BRZ_COMPANY_HUB, BRZ_COMP_EMAILS, BRZ_COMP_EMAIL_DELIVERABILITY)
       ↓
  SP_REFRESH_EMAIL_QUALITY_SUMMARY  (runs weekly via Snowflake Task)
       ↓
  BI.DW.DQ_EMAIL_QUALITY_SUMMARY    (13 rows/week — country-level metrics, history kept)
  BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN   (email count by source × country)
  BI.DW.DQ_EMAIL_GLOBAL_SUMMARY     (1 row/week — global counts + quality score)
  BI.DW.DQ_EMAIL_QUALITY_DELTA      (91 rows/week — week-over-week issue changes)
       ↓
  QuickSight — 4 SPICE datasets + 1 custom SQL dataset
       ↓
  Dashboard — 4 tabs
```

---

## How Counts Are Defined

This is the most important section. The three numbers that matter:

| Metric | Definition | Source |
|--------|-----------|--------|
| `TOTAL_COMPANIES` | Distinct companies HQ'd in this country (`COUNT DISTINCT h.ID WHERE h.HQ_COUNTRY = X`) | `BRZ_COMPANY_HUB` |
| `WITH_EMAIL` | Of those, how many have at least 1 email **tagged to this country** (`e.COUNTRY = h.HQ_COUNTRY`) | Join with `BRZ_COMP_EMAILS` |
| `HAS_EMAIL_OTHER_MARKET` | Companies with no email for this market but have an email tagged to a *different* country | Diagnostic only |

**Why `e.COUNTRY = h.HQ_COUNTRY` matters:**
`BRZ_COMP_EMAILS.COUNTRY` is the market the email belongs to, not just where the company is HQ'd.
A company HQ'd in AU with only a US-tagged email would count as **missing** for AU coverage.
This is the correct definition: "does this company have an email available for this specific market."

**What the raw counts mean (verified 2026-06-16):**
- `SELECT COUNT(DISTINCT ID) FROM BRZ_COMPANY_HUB` = **15.1M** → all companies, no market filter, not useful on its own
- `SELECT COUNT(DISTINCT ID) FROM BRZ_COMP_EMAILS` = **3.2M** → distinct companies with any email, no market filter
- These two numbers are NOT comparable. Always filter by `HQ_COUNTRY` when doing per-market analysis.

**Verified correct numbers (as of 2026-06-16):**

| Country | Total Companies | With Email | Coverage % | Has Email Other Market |
|---------|----------------|-----------|-----------|----------------------|
| US | 9,064,254 | 1,218,260 | 13.44% | 101,448 |
| AU | 1,337,465 | 743,378 | 55.58% | 2,447 |
| JP | 1,273,949 | 253,690 | 19.91% | 589 |
| CA | 1,006,338 | 148,972 | 14.80% | 11,747 |
| ID | 255,737 | 79,576 | 31.12% | 480 |
| NZ | 191,051 | 110,514 | 57.85% | 1,302 |
| SG | 167,705 | 54,390 | 32.43% | 1,138 |
| MY | 133,763 | 68,199 | 50.98% | 437 |
| HK | 122,993 | 34,078 | 27.71% | 787 |
| KR | 102,106 | 19,483 | 19.08% | 380 |
| TH | 72,441 | 46,372 | 64.01% | 469 |
| PH | 64,463 | 23,128 | 35.88% | 335 |
| VN | 20,544 | 12,608 | 61.37% | 528 |

---

## Column Reference

| Column | What it means |
|--------|--------------|
| `TOTAL_COMPANIES` | Distinct companies HQ'd in this country |
| `WITH_EMAIL` | Companies with ≥1 email tagged to this country |
| `MISSING_EMAIL` | Companies with zero emails for this country |
| `HAS_EMAIL_OTHER_MARKET` | Missing here but has email in another market — diagnostic |
| `TOTAL_EMAIL_ROWS` | Raw email row count — a company with 3 emails contributes 3 |
| `COMPANIES_WITH_FQDN` | Companies with a website domain (FQDN not null) |
| `HAS_FQDN_NO_EMAIL` | Has website domain but zero emails — highest-confidence backfill targets |
| `PCT_WITH_EMAIL` | % of total companies that have at least 1 email |
| `PCT_FQDN_NO_EMAIL` | % of FQDN companies with no email |
| `SPECIFIC_COMPANY` | Emails like john@acme.com — best quality |
| `GENERIC_ROLE_BASED` | Emails like info@, contact@, sales@ |
| `SYSTEM_BLOCKED` | noreply@, bounce@, donotreply@ — must be suppressed |
| `FREE_PROVIDER` | @gmail.com, @yahoo.com etc |

---

## Step 1 — Create the 4 Tables

Run once. `CREATE TABLE IF NOT EXISTS` is safe to re-run.

```sql
-- ── Table 1: Country-level summary ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS BI.DW.DQ_EMAIL_QUALITY_SUMMARY (
    RUN_DATE                DATE,
    COUNTRY                 VARCHAR,

    -- Universe counts
    TOTAL_COMPANIES          NUMBER,  -- distinct companies HQ'd in this country
    WITH_EMAIL               NUMBER,  -- have ≥1 email tagged to this country
    MISSING_EMAIL            NUMBER,  -- zero emails for this country
    PCT_WITH_EMAIL           FLOAT,
    PCT_MISSING              FLOAT,
    HAS_EMAIL_OTHER_MARKET   NUMBER,  -- missing here but has email in another market

    -- Source gap: has website domain but no email
    COMPANIES_WITH_FQDN      NUMBER,
    HAS_FQDN_NO_EMAIL        NUMBER,
    HAS_FQDN_WITH_EMAIL      NUMBER,
    PCT_FQDN_NO_EMAIL        FLOAT,

    -- Email row counts (raw — all emails, no capping)
    TOTAL_EMAIL_ROWS         NUMBER,
    SPECIFIC_COMPANY         NUMBER,
    GENERIC_ROLE_BASED       NUMBER,
    SYSTEM_BLOCKED           NUMBER,
    FREE_PROVIDER            NUMBER,
    PCT_SPECIFIC             FLOAT,
    PCT_GENERIC              FLOAT,
    PCT_SYSTEM_BLOCKED       FLOAT,
    PCT_FREE_PROVIDER        FLOAT,

    -- Verification status
    UNVERIFIED               NUMBER,
    HIGHLY_LIKELY            NUMBER,
    LIKELY                   NUMBER,
    UNSURE                   NUMBER,
    PCT_UNVERIFIED           FLOAT,

    -- Deliverability
    UNDELIVERABLE            NUMBER,
    DELIV_HIGHLY_LIKELY      NUMBER,
    DELIV_LIKELY             NUMBER,
    DELIV_UNSURE             NUMBER,
    NOT_CHECKED              NUMBER,
    PCT_UNDELIVERABLE        FLOAT,
    PCT_NOT_CHECKED          FLOAT,

    -- Domain mismatch
    DOMAIN_PAIRS             NUMBER,
    DOMAIN_MATCH             NUMBER,
    DOMAIN_MISMATCH          NUMBER,
    PCT_MISMATCH             FLOAT,

    -- Excessive emails (>5 per company — monitoring only, no capping in table)
    COMPANY_COUNTRY_PAIRS    NUMBER,
    COMPANIES_GT5_EMAILS     NUMBER,
    PCT_GT5                  FLOAT,

    PRIMARY KEY (RUN_DATE, COUNTRY)
);

-- ── Table 2: Source breakdown ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN (
    RUN_DATE       DATE,
    COUNTRY        VARCHAR,
    SOURCE         VARCHAR,
    EMAIL_COUNT    NUMBER,
    PCT_OF_COUNTRY FLOAT,
    PRIMARY KEY (RUN_DATE, COUNTRY, SOURCE)
);

-- ── Table 3: Week-over-week delta ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS BI.DW.DQ_EMAIL_QUALITY_DELTA (
    RUN_DATE     DATE,
    COUNTRY      VARCHAR,
    CATEGORY     VARCHAR,    -- 'Coverage' | 'Quality' | 'Noise'
    ISSUE        VARCHAR,
    PREV_COUNT   NUMBER,
    CURR_COUNT   NUMBER,
    DELTA        NUMBER,     -- negative = improved (fewer bad records)
    DELTA_PCT    FLOAT,
    DIRECTION    VARCHAR,    -- 'IMPROVED' | 'WORSENED' | 'NO CHANGE'
    ROOT_CAUSE   VARCHAR,    -- auto-mapped from issue type (static lookup)
    SCORE_IMPACT FLOAT,      -- estimated pts change in overall quality score
    PRIMARY KEY (RUN_DATE, COUNTRY, ISSUE)
);

-- ── Table 4: Global summary (one row per run date) ────────────────────────────
CREATE TABLE IF NOT EXISTS BI.DW.DQ_EMAIL_GLOBAL_SUMMARY (
    RUN_DATE                   DATE PRIMARY KEY,
    TOTAL_DISTINCT_COMPANIES   NUMBER,  -- COUNT(DISTINCT ID) — ALL companies globally, no filter (15.1M)
    TOTAL_MARKETS_13           NUMBER,  -- COUNT(DISTINCT ID) filtered to 13 markets (13.8M)
    TOTAL_NO_LOCATION          NUMBER,  -- companies with NULL HQ_COUNTRY (1.1M)
    TOTAL_COMPANY_COUNTRY_RECS NUMBER,  -- sum of per-country totals
    OVERALL_QUALITY_SCORE      FLOAT,   -- weighted: Coverage×0.5 + Accuracy×0.3 + Consistency×0.2
    AVG_COVERAGE_PCT           FLOAT,
    AVG_ACCURACY_PCT           FLOAT,   -- 100 - AVG(PCT_MISMATCH)
    AVG_CONSISTENCY_PCT        FLOAT    -- AVG(PCT_SPECIFIC)
);
```

---

## Step 2 — Create the Stored Procedure

```sql
CREATE OR REPLACE PROCEDURE BI.DW.SP_REFRESH_EMAIL_QUALITY_SUMMARY()
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    v_run_date DATE DEFAULT CURRENT_DATE();
BEGIN

    DELETE FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY    WHERE RUN_DATE = :v_run_date;
    DELETE FROM BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN   WHERE RUN_DATE = :v_run_date;
    DELETE FROM BI.DW.DQ_EMAIL_GLOBAL_SUMMARY     WHERE RUN_DATE = :v_run_date;
    DELETE FROM BI.DW.DQ_EMAIL_QUALITY_DELTA      WHERE RUN_DATE = :v_run_date;

    -- ── Table 1: Country summary ──────────────────────────────────────────────
    -- WITH_EMAIL = companies that have ≥1 email where e.COUNTRY = h.HQ_COUNTRY
    -- This is market-specific coverage: an AU company must have an AU-tagged email
    INSERT INTO BI.DW.DQ_EMAIL_QUALITY_SUMMARY (
        RUN_DATE, COUNTRY,
        TOTAL_COMPANIES, WITH_EMAIL, MISSING_EMAIL, PCT_WITH_EMAIL, PCT_MISSING, HAS_EMAIL_OTHER_MARKET,
        COMPANIES_WITH_FQDN, HAS_FQDN_NO_EMAIL, HAS_FQDN_WITH_EMAIL, PCT_FQDN_NO_EMAIL,
        TOTAL_EMAIL_ROWS, SPECIFIC_COMPANY, GENERIC_ROLE_BASED, SYSTEM_BLOCKED, FREE_PROVIDER,
        PCT_SPECIFIC, PCT_GENERIC, PCT_SYSTEM_BLOCKED, PCT_FREE_PROVIDER,
        UNVERIFIED, HIGHLY_LIKELY, LIKELY, UNSURE, PCT_UNVERIFIED,
        UNDELIVERABLE, DELIV_HIGHLY_LIKELY, DELIV_LIKELY, DELIV_UNSURE, NOT_CHECKED,
        PCT_UNDELIVERABLE, PCT_NOT_CHECKED,
        DOMAIN_PAIRS, DOMAIN_MATCH, DOMAIN_MISMATCH, PCT_MISMATCH,
        COMPANY_COUNTRY_PAIRS, COMPANIES_GT5_EMAILS, PCT_GT5
    )
    WITH countries AS (
        SELECT * FROM (VALUES
            ('US'),('CA'),('AU'),('NZ'),('SG'),('MY'),
            ('PH'),('ID'),('JP'),('HK'),('TH'),('VN'),('KR')
        ) t(country)
    ),
    coverage AS (
        -- Market-specific: e.COUNTRY must match h.HQ_COUNTRY
        SELECT
            h.HQ_COUNTRY                                                                   AS country,
            COUNT(DISTINCT h.ID)                                                           AS total_companies,
            COUNT(DISTINCT CASE WHEN e_hq.ID IS NOT NULL THEN h.ID END)                    AS with_email,
            COUNT(DISTINCT CASE WHEN e_hq.ID IS NULL     THEN h.ID END)                    AS missing_email,
            ROUND(100.0 * COUNT(DISTINCT CASE WHEN e_hq.ID IS NOT NULL THEN h.ID END)
                  / NULLIF(COUNT(DISTINCT h.ID), 0), 2)                                    AS pct_with_email,
            ROUND(100.0 * COUNT(DISTINCT CASE WHEN e_hq.ID IS NULL THEN h.ID END)
                  / NULLIF(COUNT(DISTINCT h.ID), 0), 2)                                    AS pct_missing,
            COUNT(DISTINCT CASE WHEN e_hq.ID IS NULL AND e_any.ID IS NOT NULL
                                THEN h.ID END)                                             AS has_email_other_market
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
        LEFT JOIN (
            SELECT DISTINCT ID, COUNTRY
            FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
            WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
        ) e_hq ON h.ID = e_hq.ID AND h.HQ_COUNTRY = e_hq.COUNTRY
        LEFT JOIN (
            SELECT DISTINCT ID
            FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
            WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
        ) e_any ON h.ID = e_any.ID
        WHERE h.HQ_COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
        GROUP BY h.HQ_COUNTRY
    ),
    fqdn_gap AS (
        SELECT h.HQ_COUNTRY AS country,
            COUNT(DISTINCT h.ID) AS companies_with_fqdn,
            COUNT(DISTINCT CASE WHEN e.EMAIL IS NULL     THEN h.ID END) AS has_fqdn_no_email,
            COUNT(DISTINCT CASE WHEN e.EMAIL IS NOT NULL THEN h.ID END) AS has_fqdn_with_email,
            ROUND(100.0*COUNT(DISTINCT CASE WHEN e.EMAIL IS NULL THEN h.ID END)/NULLIF(COUNT(DISTINCT h.ID),0),2) AS pct_fqdn_no_email
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
        LEFT JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e
            ON h.ID=e.ID AND e.COUNTRY=h.HQ_COUNTRY
        WHERE h.HQ_COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
          AND h.FQDN IS NOT NULL AND TRIM(h.FQDN)<>''
        GROUP BY h.HQ_COUNTRY
    ),
    email_types AS (
        SELECT COUNTRY,
            COUNT(*) AS total_email_rows,
            SUM(CASE WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*') THEN 1 ELSE 0 END) AS system_blocked,
            SUM(CASE WHEN REGEXP_LIKE(LOWER(TRIM(EMAIL)),'@(gmail[.]com|yahoo[.]com|hotmail[.]com|outlook[.]com|icloud[.]com|live[.]com|aol[.]com|protonmail[.]com|mail[.]com|yahoo[.]co[.]jp|yahoo[.]co[.]id|naver[.]com|daum[.]net|kakao[.]com)') THEN 1 ELSE 0 END) AS free_provider,
            SUM(CASE WHEN NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*')
                 AND NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),'@(gmail[.]com|yahoo[.]com|hotmail[.]com|outlook[.]com|icloud[.]com|live[.]com|aol[.]com|protonmail[.]com|mail[.]com|yahoo[.]co[.]jp|yahoo[.]co[.]id|naver[.]com|daum[.]net|kakao[.]com)')
                 AND REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(admin|webmaster|hostmaster|root|support|info|hello|help|contact|sales|enquir|billing|accounts|hr|careers|jobs|marketing|press|media|legal|privacy|service|team|office|reception|general|enquiries|customerservice|cs|operations)@.*')
                 THEN 1 ELSE 0 END) AS generic_role_based,
            SUM(CASE WHEN NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(noreply|no-reply|donotreply|do-not-reply|bounce|unsubscribe|mailer-daemon|postmaster|abuse|spam)@.*')
                 AND NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),'@(gmail[.]com|yahoo[.]com|hotmail[.]com|outlook[.]com|icloud[.]com|live[.]com|aol[.]com|protonmail[.]com|mail[.]com|yahoo[.]co[.]jp|yahoo[.]co[.]id|naver[.]com|daum[.]net|kakao[.]com)')
                 AND NOT REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^(admin|webmaster|hostmaster|root|support|info|hello|help|contact|sales|enquir|billing|accounts|hr|careers|jobs|marketing|press|media|legal|privacy|service|team|office|reception|general|enquiries|customerservice|cs|operations)@.*')
                 THEN 1 ELSE 0 END) AS specific_company
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
        WHERE COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
          AND EMAIL IS NOT NULL AND TRIM(EMAIL)<>''
          AND REGEXP_LIKE(LOWER(TRIM(EMAIL)),'^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')
        GROUP BY COUNTRY
    ),
    verification AS (
        SELECT COUNTRY,
            SUM(CASE WHEN VERIFICATION_STATUS IS NULL OR TRIM(VERIFICATION_STATUS)='' THEN 1 ELSE 0 END) AS unverified,
            SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Highly likely' THEN 1 ELSE 0 END) AS highly_likely,
            SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Likely'        THEN 1 ELSE 0 END) AS likely,
            SUM(CASE WHEN TRIM(VERIFICATION_STATUS)='Unsure'        THEN 1 ELSE 0 END) AS unsure,
            ROUND(100.0*SUM(CASE WHEN VERIFICATION_STATUS IS NULL OR TRIM(VERIFICATION_STATUS)='' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_unverified
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
        WHERE COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
        GROUP BY COUNTRY
    ),
    deliverability AS (
        SELECT COUNTRY,
            SUM(CASE WHEN DELIVERABILITY='em-av-undeliverable' THEN 1 ELSE 0 END) AS undeliverable,
            SUM(CASE WHEN DELIVERABILITY='em-av-highly-likely' THEN 1 ELSE 0 END) AS deliv_highly_likely,
            SUM(CASE WHEN DELIVERABILITY='em-av-likely'        THEN 1 ELSE 0 END) AS deliv_likely,
            SUM(CASE WHEN DELIVERABILITY='em-av-unsure'        THEN 1 ELSE 0 END) AS deliv_unsure,
            SUM(CASE WHEN DELIVERABILITY IS NULL               THEN 1 ELSE 0 END) AS not_checked,
            ROUND(100.0*SUM(CASE WHEN DELIVERABILITY='em-av-undeliverable' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_undeliverable,
            ROUND(100.0*SUM(CASE WHEN DELIVERABILITY IS NULL               THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_not_checked
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAIL_DELIVERABILITY
        WHERE COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
        GROUP BY COUNTRY
    ),
    mismatch AS (
        SELECT h.HQ_COUNTRY AS country, COUNT(*) AS domain_pairs,
            SUM(CASE WHEN SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)=SPLIT_PART(SPLIT_PART(LOWER(TRIM(e.EMAIL)),'@',2),'.',1) AND SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)<>'' THEN 1 ELSE 0 END) AS domain_match,
            SUM(CASE WHEN SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)<>SPLIT_PART(SPLIT_PART(LOWER(TRIM(e.EMAIL)),'@',2),'.',1) OR SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)='' THEN 1 ELSE 0 END) AS domain_mismatch,
            ROUND(100.0*SUM(CASE WHEN SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)<>SPLIT_PART(SPLIT_PART(LOWER(TRIM(e.EMAIL)),'@',2),'.',1) OR SPLIT_PART(LOWER(TRIM(h.FQDN)),'.',1)='' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_mismatch
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
        JOIN FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e ON h.ID=e.ID AND e.COUNTRY=h.HQ_COUNTRY
        WHERE h.HQ_COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
          AND h.FQDN IS NOT NULL AND TRIM(h.FQDN)<>'' AND h.FQDN LIKE '%.%'
          AND e.EMAIL IS NOT NULL AND e.EMAIL LIKE '%@%'
        GROUP BY h.HQ_COUNTRY
    ),
    excessive AS (
        WITH per_co AS (
            SELECT ID, COUNTRY,
                SUM(CASE WHEN EMAIL IS NOT NULL AND TRIM(EMAIL)<>'' THEN 1 ELSE 0 END) AS ecnt
            FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
            WHERE COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
            GROUP BY ID, COUNTRY
        )
        SELECT COUNTRY, COUNT(*) AS company_country_pairs,
            SUM(CASE WHEN ecnt>5 THEN 1 ELSE 0 END) AS companies_gt5,
            ROUND(100.0*SUM(CASE WHEN ecnt>5 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) AS pct_gt5
        FROM per_co GROUP BY COUNTRY
    )
    SELECT :v_run_date,
        c.country,
        cov.total_companies, cov.with_email, cov.missing_email, cov.pct_with_email, cov.pct_missing, cov.has_email_other_market,
        fg.companies_with_fqdn, fg.has_fqdn_no_email, fg.has_fqdn_with_email, fg.pct_fqdn_no_email,
        et.total_email_rows, et.specific_company, et.generic_role_based, et.system_blocked, et.free_provider,
        ROUND(100.0*et.specific_company   /NULLIF(et.total_email_rows,0),2),
        ROUND(100.0*et.generic_role_based /NULLIF(et.total_email_rows,0),2),
        ROUND(100.0*et.system_blocked     /NULLIF(et.total_email_rows,0),2),
        ROUND(100.0*et.free_provider      /NULLIF(et.total_email_rows,0),2),
        v.unverified, v.highly_likely, v.likely, v.unsure, v.pct_unverified,
        d.undeliverable, d.deliv_highly_likely, d.deliv_likely, d.deliv_unsure, d.not_checked, d.pct_undeliverable, d.pct_not_checked,
        m.domain_pairs, m.domain_match, m.domain_mismatch, m.pct_mismatch,
        ex.company_country_pairs, ex.companies_gt5, ex.pct_gt5
    FROM countries c
    LEFT JOIN coverage       cov ON cov.country=c.country
    LEFT JOIN fqdn_gap       fg  ON fg.country =c.country
    LEFT JOIN email_types    et  ON et.country =c.country
    LEFT JOIN verification   v   ON v.country  =c.country
    LEFT JOIN deliverability d   ON d.country  =c.country
    LEFT JOIN mismatch       m   ON m.country  =c.country
    LEFT JOIN excessive      ex  ON ex.country =c.country;

    -- ── Table 2: Source breakdown ─────────────────────────────────────────────
    INSERT INTO BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN (RUN_DATE, COUNTRY, SOURCE, EMAIL_COUNT, PCT_OF_COUNTRY)
    WITH totals AS (
        SELECT COUNTRY, COUNT(*) AS total
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
        WHERE COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
        GROUP BY COUNTRY
    )
    SELECT :v_run_date,
        e.COUNTRY,
        COALESCE(NULLIF(TRIM(e.SOURCE),''),'NULL') AS source,
        COUNT(*) AS email_count,
        ROUND(100.0*COUNT(*)/NULLIF(t.total,0),2) AS pct_of_country
    FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS e
    JOIN totals t ON t.COUNTRY=e.COUNTRY
    WHERE e.COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR')
    GROUP BY e.COUNTRY, COALESCE(NULLIF(TRIM(e.SOURCE),''),'NULL'), t.total;

    -- ── Table 4: Global summary ───────────────────────────────────────────────
    INSERT INTO BI.DW.DQ_EMAIL_GLOBAL_SUMMARY (
        RUN_DATE, TOTAL_DISTINCT_COMPANIES, TOTAL_MARKETS_13, TOTAL_NO_LOCATION,
        TOTAL_COMPANY_COUNTRY_RECS, OVERALL_QUALITY_SCORE,
        AVG_COVERAGE_PCT, AVG_ACCURACY_PCT, AVG_CONSISTENCY_PCT
    )
    WITH global AS (
        SELECT
            COUNT(DISTINCT ID)                                                                        AS total_all,
            COUNT(DISTINCT CASE WHEN HQ_COUNTRY IN ('US','CA','AU','NZ','SG','MY','PH','ID','JP','HK','TH','VN','KR') THEN ID END) AS total_markets_13,
            COUNT(DISTINCT CASE WHEN HQ_COUNTRY IS NULL THEN ID END)                                  AS total_no_location
        FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB
    ),
    agg AS (
        SELECT
            SUM(TOTAL_COMPANIES)    AS total_co_country_recs,
            AVG(PCT_WITH_EMAIL)     AS avg_coverage,
            100 - AVG(PCT_MISMATCH) AS avg_accuracy,
            AVG(PCT_SPECIFIC)       AS avg_consistency
        FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY
        WHERE RUN_DATE = :v_run_date
    )
    SELECT
        :v_run_date,
        g.total_all,
        g.total_markets_13,
        g.total_no_location,
        a.total_co_country_recs,
        ROUND(a.avg_coverage * 0.5 + a.avg_accuracy * 0.3 + a.avg_consistency * 0.2, 2),
        ROUND(a.avg_coverage, 2),
        ROUND(a.avg_accuracy, 2),
        ROUND(a.avg_consistency, 2)
    FROM global g CROSS JOIN agg a;

    -- ── Table 3: Week-over-week delta (needs 2 weeks of data — 0 rows on first run) ──
    -- ROOT_CAUSE is a static lookup per issue type — no manual input needed
    -- SCORE_IMPACT estimates contribution to overall quality score change
    INSERT INTO BI.DW.DQ_EMAIL_QUALITY_DELTA (
        RUN_DATE, COUNTRY, CATEGORY, ISSUE, PREV_COUNT, CURR_COUNT, DELTA, DELTA_PCT, DIRECTION, ROOT_CAUSE, SCORE_IMPACT
    )
    WITH curr AS (
        SELECT * FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY WHERE RUN_DATE = :v_run_date
    ),
    prev AS (
        SELECT * FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY
        WHERE RUN_DATE = (
            SELECT MAX(RUN_DATE) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY WHERE RUN_DATE < :v_run_date
        )
    ),
    issues AS (
        SELECT c.COUNTRY, 'Coverage' AS category, 'Missing Email'    AS issue, p.MISSING_EMAIL    AS prev_count, c.MISSING_EMAIL    AS curr_count, p.TOTAL_COMPANIES AS base FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Coverage', 'Domain Gap',         p.HAS_FQDN_NO_EMAIL,  c.HAS_FQDN_NO_EMAIL,  p.COMPANIES_WITH_FQDN FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Quality',  'Unverified',         p.UNVERIFIED,          c.UNVERIFIED,          p.TOTAL_EMAIL_ROWS    FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Quality',  'Undeliverable',      p.UNDELIVERABLE,       c.UNDELIVERABLE,       p.TOTAL_EMAIL_ROWS    FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Quality',  'Never Checked',      p.NOT_CHECKED,         c.NOT_CHECKED,         p.TOTAL_EMAIL_ROWS    FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Quality',  'Domain Mismatch',    p.DOMAIN_MISMATCH,     c.DOMAIN_MISMATCH,     p.DOMAIN_PAIRS        FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
        UNION ALL SELECT c.COUNTRY, 'Noise',    'Generic Role-Based', p.GENERIC_ROLE_BASED,  c.GENERIC_ROLE_BASED,  p.TOTAL_EMAIL_ROWS    FROM curr c JOIN prev p ON c.COUNTRY=p.COUNTRY
    ),
    root_causes(issue, root_cause, score_weight) AS (
        SELECT * FROM (VALUES
            ('Missing Email',    'Companies in this market have no email tagged to their HQ country — source pipeline gap or no ingestion coverage', 0.5),
            ('Domain Gap',       'Company has a website domain (FQDN) but no email — highest-confidence backfill target via domain scraping', 0.5),
            ('Unverified',       'Emails were ingested but never run through the verifier waterfall (Findymail → Million Verifier → BounceBan)', 0.3),
            ('Undeliverable',    'Verifier returned em-av-undeliverable — these emails are live in product and causing hard bounces', 0.3),
            ('Never Checked',    'Emails have no deliverability record — verifier waterfall has not been triggered for this market or source', 0.3),
            ('Domain Mismatch',  'Email domain does not match company FQDN — likely GMAPS crawl assigning one domain''s emails to all companies on that block', 0.3),
            ('Generic Role-Based','info@/contact@/sales@ emails ranked above specific emails — type-based ranking not applied at ingestion', 0.2)
        ) t(issue, root_cause, score_weight)
    )
    SELECT :v_run_date,
        i.COUNTRY, i.category, i.issue, i.prev_count, i.curr_count,
        i.curr_count - i.prev_count AS delta,
        ROUND(100.0*(i.curr_count - i.prev_count)/NULLIF(i.prev_count, 0), 2) AS delta_pct,
        CASE
            WHEN i.curr_count < i.prev_count THEN 'IMPROVED'
            WHEN i.curr_count > i.prev_count THEN 'WORSENED'
            ELSE 'NO CHANGE'
        END AS direction,
        rc.root_cause,
        -- Score impact: how much did this issue's change move the weighted quality dimension?
        ROUND(
            ABS(i.curr_count - i.prev_count) / NULLIF(i.base, 0) * 100.0 * rc.score_weight,
        2) AS score_impact
    FROM issues i
    LEFT JOIN root_causes rc ON rc.issue = i.issue;

    RETURN 'Done: ' || :v_run_date;
END;
$$;
```

---

## Step 3 — Seed and Verify

```sql
-- Run the procedure once
CALL BI.DW.SP_REFRESH_EMAIL_QUALITY_SUMMARY();

-- Verify row counts
SELECT COUNT(*) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY;   -- expect 13
SELECT COUNT(*) FROM BI.DW.DQ_EMAIL_SOURCE_BREAKDOWN;  -- varies
SELECT COUNT(*) FROM BI.DW.DQ_EMAIL_GLOBAL_SUMMARY;    -- expect 1
SELECT COUNT(*) FROM BI.DW.DQ_EMAIL_QUALITY_DELTA;     -- 0 on first run (expected)

-- Spot-check coverage numbers against verified baseline (2026-06-16)
SELECT COUNTRY, TOTAL_COMPANIES, WITH_EMAIL, PCT_WITH_EMAIL
FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY
ORDER BY TOTAL_COMPANIES DESC;
-- AU should show: 1,337,465 total | 743,378 with email | 55.58%
-- US should show: 9,064,254 total | 1,218,260 with email | 13.44%
```

---

## Step 4 — Schedule Weekly Refresh

```sql
CREATE OR REPLACE TASK BI.DW.TASK_EMAIL_QUALITY_WEEKLY
    WAREHOUSE = BI_TEAM
    SCHEDULE  = 'USING CRON 30 12 * * 5 Asia/Kolkata'
AS
    CALL BI.DW.SP_REFRESH_EMAIL_QUALITY_SUMMARY();

ALTER TASK BI.DW.TASK_EMAIL_QUALITY_WEEKLY RESUME;

-- Verify active
SHOW TASKS LIKE 'TASK_EMAIL_QUALITY_WEEKLY' IN SCHEMA BI.DW;
```

---

## Step 5 — Connect QuickSight

1. **QuickSight → Datasets → New dataset → Snowflake**
2. Connection: Server `SYPBXPR-CZ72457.snowflakecomputing.com` / Database `BI` / Schema `DW`
3. Create **4 SPICE datasets** + 1 custom SQL:

| Dataset name | Table | Mode |
|---|---|---|
| Email Quality Summary | `DQ_EMAIL_QUALITY_SUMMARY` | SPICE |
| Email Source Breakdown | `DQ_EMAIL_SOURCE_BREAKDOWN` | SPICE |
| Email Global Summary | `DQ_EMAIL_GLOBAL_SUMMARY` | SPICE |
| Email Quality Delta | `DQ_EMAIL_QUALITY_DELTA` | SPICE |
| Email Issues Unpivoted | Custom SQL below | SPICE |

4. SPICE refresh: **Weekly, Friday at 7:30 PM IST** (1 hour after Snowflake task)

**Custom SQL — Email Issues Unpivoted (for Issues tab bar chart):**
```sql
SELECT s.RUN_DATE, s.COUNTRY, s.TOTAL_COMPANIES, s.TOTAL_EMAIL_ROWS,
    'Coverage' AS category, 'Missing Email' AS issue,
    s.MISSING_EMAIL AS affected,
    ROUND(100.0*s.MISSING_EMAIL/NULLIF(s.TOTAL_COMPANIES,0),2) AS pct_affected
FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Coverage','Domain Gap',
    s.HAS_FQDN_NO_EMAIL,ROUND(100.0*s.HAS_FQDN_NO_EMAIL/NULLIF(s.COMPANIES_WITH_FQDN,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Quality','Unverified',
    s.UNVERIFIED,ROUND(100.0*s.UNVERIFIED/NULLIF(s.TOTAL_EMAIL_ROWS,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Quality','Undeliverable',
    s.UNDELIVERABLE,ROUND(100.0*s.UNDELIVERABLE/NULLIF(s.TOTAL_EMAIL_ROWS,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Quality','Never Checked',
    s.NOT_CHECKED,ROUND(100.0*s.NOT_CHECKED/NULLIF(s.TOTAL_EMAIL_ROWS,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Quality','Domain Mismatch',
    s.DOMAIN_MISMATCH,ROUND(100.0*s.DOMAIN_MISMATCH/NULLIF(s.DOMAIN_PAIRS,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
UNION ALL SELECT s.RUN_DATE,s.COUNTRY,s.TOTAL_COMPANIES,s.TOTAL_EMAIL_ROWS,'Noise','Generic Role-Based',
    s.GENERIC_ROLE_BASED,ROUND(100.0*s.GENERIC_ROLE_BASED/NULLIF(s.TOTAL_EMAIL_ROWS,0),2) FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY s
```

---

## Step 6 — Build the Dashboard (4 Tabs)

### Filter Bar (Pinned — All Tabs)

| Control | Type | Default |
|---------|------|---------|
| Country | Multi-select | All 13 |
| Issue Category | Toggle: `All · Coverage · Quality · Noise` | All |
| Date | Week picker | Latest `RUN_DATE` |

---

### Tab 1 — Overview
*Dataset: Email Global Summary + Email Quality Summary*

**Row A — Universe counts**
| KPI | Metric |
|-----|--------|
| Total Companies (13 markets) | `SUM(TOTAL_COMPANIES)` |
| Companies with Email | `SUM(WITH_EMAIL)` |
| Companies without Email | `SUM(MISSING_EMAIL)` |
| Has Email Other Market | `SUM(HAS_EMAIL_OTHER_MARKET)` |
| Coverage % | `AVG(PCT_WITH_EMAIL)` |

**Row B — Quality Score**
| KPI | Metric | Weight |
|-----|--------|--------|
| Overall Quality Score | `OVERALL_QUALITY_SCORE` | — |
| Coverage | `AVG_COVERAGE_PCT` | 50% |
| Accuracy (domain match) | `AVG_ACCURACY_PCT` | 30% |
| Consistency (specific emails) | `AVG_CONSISTENCY_PCT` | 20% |

---

### Tab 2 — By Country
*Dataset: Email Quality Summary*

**V1 — Coverage by Country (stacked bar)**
- Y-axis: `COUNTRY` sorted by `MISSING_EMAIL` desc
- Segments: `WITH_EMAIL` (green) + `MISSING_EMAIL` (red)
- Tooltip: also show `HAS_EMAIL_OTHER_MARKET`

**V2 — Coverage % by Country (vertical bar)**
- X: `COUNTRY` sorted by `PCT_WITH_EMAIL` asc, Y: `PCT_WITH_EMAIL`
- Reference line at 70% (target)

**V3 — Quality Score by Country (combo chart)**
- Grouped bars: Coverage % / Accuracy % / Consistency %
- Line overlay: `QUALITY_SCORE = PCT_WITH_EMAIL*0.5 + (100-PCT_MISMATCH)*0.3 + PCT_SPECIFIC*0.2`

---

### Tab 3 — Issues
*Datasets: Email Quality Summary + Email Issues Unpivoted*

**V4 — Issues Summary Table**
Columns: `Category` | `Issue` | `# Affected` | `% of Base` | `Trend vs last week`
Conditional color on %: ≥20% Red | 5–19% Amber | <5% Green

**V5 — Issues Ranked (horizontal bar)**
Y-axis: `ISSUE` sorted by `PCT_AFFECTED` desc, color by `CATEGORY`

---

### Tab 4 — Trends
*Datasets: Email Global Summary + Email Quality Delta*

**Row A — KPI cards (4 cards)**
| Card | Metric | Delta label |
|------|--------|-------------|
| Overall Quality Score | `OVERALL_QUALITY_SCORE` (latest) | vs prior week |
| Coverage | `AVG_COVERAGE_PCT` (latest) | vs prior week |
| Accuracy | `AVG_ACCURACY_PCT` (latest) | vs prior week |
| Consistency | `AVG_CONSISTENCY_PCT` (latest) | vs prior week |

QuickSight calculated field for delta: `[metric this week] - [metric last week]`
Show green arrow if positive, red if negative.

**V6 — Coverage + Accuracy + Consistency Trend (line chart)**
X: `RUN_DATE`, three lines:
- Coverage %: `AVG_COVERAGE_PCT` — blue
- Accuracy %: `AVG_ACCURACY_PCT` — purple
- Consistency %: `AVG_CONSISTENCY_PCT` — green

Add a reference annotation (vertical dashed line) for any week where `DQ_EMAIL_QUALITY_DELTA` has ≥1 row with `DIRECTION = 'IMPROVED'`.

**V7 — Overall Quality Score Trend (separate line chart)**
X: `RUN_DATE`, Y: `OVERALL_QUALITY_SCORE` (single line, navy)
This is kept separate from V6 so the score trend is not visually mixed with the dimension trends.

**V8 — What Changed (table visual)**
*Dataset: Email Quality Delta — filter: `DIRECTION = 'IMPROVED'`*

Columns:
| Column | Source |
|--------|--------|
| Week | `RUN_DATE` |
| Country | `COUNTRY` |
| Issue | `ISSUE` |
| # Resolved | `ABS(DELTA)` |
| Root Cause | `ROOT_CAUSE` — auto from SP |
| Score Impact | `SCORE_IMPACT` pts — auto from SP |
| Status | Calculated field: `ifelse({DIRECTION} = 'IMPROVED', 'Done', 'Pending')` |

All columns are auto-populated by the stored procedure — no manual input.
Rows with `DIRECTION = 'WORSENED'` also visible when filter is set to "All" — shows regressions too.

**V9 — Open Issues (table visual)**
*Dataset: Email Quality Delta — filter: `DIRECTION = 'WORSENED' OR DIRECTION = 'NO CHANGE'`, latest week only*

Columns: `Country` | `Issue` | `Category` | `# Affected (curr)` | `Root Cause` | `Score Impact`
Purpose: shows what still needs to be fixed this week.

---

### Top 5 Emails per Company — QuickSight Filter

All emails are stored in the source tables without capping. When building a visual that shows individual emails per company, apply this rank filter in QuickSight:

```
Calculated field: email_rank
= rank(
    [{company_id}],
    [{is_system_blocked} ASC, {is_free_provider} ASC, {is_specific} DESC, {deliverability_score} DESC]
  )

Filter on visual: email_rank <= 5
```

This means:
- Snowflake stores every email row — no rows deleted or capped
- QuickSight shows only the top 5 per company when the visual requires it
- Rankings update automatically on next SPICE refresh

---

## Summary

| Table | Rows per run | Purpose |
|-------|-------------|---------|
| `DQ_EMAIL_QUALITY_SUMMARY` | 13 | Country-level metrics, full history |
| `DQ_EMAIL_SOURCE_BREAKDOWN` | varies | Email count by source × country |
| `DQ_EMAIL_GLOBAL_SUMMARY` | 1 | Global counts + weighted quality score |
| `DQ_EMAIL_QUALITY_DELTA` | 91 (13×7) | Week-over-week issue changes |

| Component | Schedule |
|-----------|----------|
| Snowflake SP + Task | Weekly — Friday 6 PM IST |
| QuickSight SPICE (5 datasets) | Weekly — Friday 7:30 PM IST |

---

## Troubleshooting

### Table 3 (Delta) is empty on first run
Expected — needs 2 weeks of data. Populates from the second run onwards.

### Task is suspended
```sql
ALTER TASK BI.DW.TASK_EMAIL_QUALITY_WEEKLY RESUME;
```

### Coverage number seems wrong — check the logic
```sql
-- Quick sanity check for AU
SELECT
    COUNT(DISTINCT h.ID) AS total_au_companies,
    COUNT(DISTINCT CASE WHEN e.ID IS NOT NULL THEN h.ID END) AS with_au_email
FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMPANY_HUB h
LEFT JOIN (
    SELECT DISTINCT ID, COUNTRY FROM FIRMOGRAPHICS.ZEUS_BRONZE.BRZ_COMP_EMAILS
    WHERE EMAIL IS NOT NULL AND TRIM(EMAIL) <> ''
) e ON h.ID = e.ID AND h.HQ_COUNTRY = e.COUNTRY
WHERE h.HQ_COUNTRY = 'AU';
-- Expected: ~1,337,465 total | ~743,378 with email
```
