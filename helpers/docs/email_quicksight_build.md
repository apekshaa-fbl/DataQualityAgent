# Email Data Quality Dashboard — QuickSight Build Guide

**Status:** Ready to build  
**Tables:** 4 SPICE datasets + 1 custom SQL  
**Refresh:** Weekly, Friday 7:30 PM IST  
**Sheets:** 3 (Overview, Issues by Country, Trends)

---

## Connection Setup (Do Once)

1. **QuickSight** → **Manage QuickSight** → ensure Snowflake VPC access is enabled
2. **Datasets** → **New dataset** → **Snowflake**
3. Connection details:
   - Server: `SYPBXPR-CZ72457.snowflakecomputing.com`
   - Database: `BI`
   - Schema: `DW`
   - Warehouse: `BI_TEAM`

---

## Step 1 — Create 4 SPICE Datasets

Create each dataset as a separate SPICE import (not DirectQuery):

### Dataset 1: Email Global Summary
1. **New dataset** → **Snowflake**
2. **Table:** `DQ_EMAIL_GLOBAL_SUMMARY`
3. **Import to SPICE** → **Create dataset**
4. **Schedule refresh:** Weekly, Friday 7:30 PM IST

### Dataset 2: Email Quality Summary
1. **New dataset** → **Snowflake**
2. **Table:** `DQ_EMAIL_QUALITY_SUMMARY`
3. **Import to SPICE** → **Create dataset**
4. **Schedule refresh:** Weekly, Friday 7:30 PM IST

### Dataset 3: Email Quality Delta
1. **New dataset** → **Snowflake**
2. **Table:** `DQ_EMAIL_QUALITY_DELTA`
3. **Import to SPICE** → **Create dataset**
4. **Schedule refresh:** Weekly, Friday 7:30 PM IST

### Dataset 4: Email Issues Unpivoted (Custom SQL)
1. **New dataset** → **Snowflake** → **Use custom SQL**
2. **Paste this query:**

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

3. **Import to SPICE** → **Create dataset**
4. **Schedule refresh:** Weekly, Friday 7:30 PM IST

---

## Step 2 — Create Dashboard & Filter Bar

1. **Create new dashboard** → name it `Email Data Quality`
2. **Add filter bar (top)** — will be visible on all sheets
3. **Add 3 filters (pinned):**
   - **Filter 1 — Country**
     - Field: `COUNTRY` (from Email Quality Summary)
     - Type: Multi-select
     - Default: All 13 countries
   - **Filter 2 — Date**
     - Field: `RUN_DATE` (from Email Global Summary)
     - Type: Date picker
     - Default: Latest
   - **Filter 3 — Category** (for Issues sheet)
     - Field: `CATEGORY` (from Email Issues Unpivoted)
     - Type: Dropdown
     - Default: All

---

## Step 3 — Build Sheet 1: Overview

### Row A — KPI Cards (10 cards)

Add 10 KPI visuals side-by-side (use 2 rows of 5 if needed):

**KPI 1 — Total Companies (Global)**
- Dataset: Email Global Summary
- Value: `TOTAL_DISTINCT_COMPANIES`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `Total Companies (Global)`

**KPI 2 — Total Companies (13 Markets)**
- Dataset: Email Global Summary
- Value: `TOTAL_MARKETS_13`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `Companies (13 Markets)`

**KPI 3 — Companies with No Location**
- Dataset: Email Global Summary
- Value: `TOTAL_NO_LOCATION`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `No Location`

**KPI 4 — Other Markets**
- Dataset: Email Global Summary
- **Calculated field:** `TOTAL_DISTINCT_COMPANIES - TOTAL_MARKETS_13 - TOTAL_NO_LOCATION`
- Name it: `OTHER_MARKETS`
- Use in KPI as: `OTHER_MARKETS` (Max)
- Title: `Other Markets`

**KPI 5 — Companies with Email (13 Markets)**
- Dataset: Email Quality Summary
- Value: `WITH_EMAIL`
- Aggregation: Sum
- Trend: `RUN_DATE`
- Title: `With Email`

**KPI 6 — Missing Email (13 Markets)**
- Dataset: Email Quality Summary
- Value: `MISSING_EMAIL`
- Aggregation: Sum
- Trend: `RUN_DATE`
- Title: `Missing Email`

**KPI 7 — Coverage %**
- Dataset: Email Quality Summary
- Value: `PCT_WITH_EMAIL`
- Aggregation: Average
- Trend: `RUN_DATE`
- Title: `Avg Coverage %`

**KPI 8 — Accuracy %**
- Dataset: Email Global Summary
- Value: `AVG_ACCURACY_PCT`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `Accuracy %`

**KPI 9 — Consistency %**
- Dataset: Email Global Summary
- Value: `AVG_CONSISTENCY_PCT`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `Consistency %`

**KPI 10 — Overall Quality Score**
- Dataset: Email Global Summary
- Value: `OVERALL_QUALITY_SCORE`
- Aggregation: Max
- Trend: `RUN_DATE`
- Title: `Quality Score`

---

### Row B — Coverage by Country (Bar Chart)

1. **Add visual** → **Bar chart**
2. Dataset: Email Quality Summary
3. **X-axis:** `COUNTRY` (sort by `PCT_WITH_EMAIL` descending)
4. **Y-axis:** `PCT_WITH_EMAIL`
5. **Title:** `Coverage % by Country`
6. **Reference line:** Y = 70 (target)
7. **Color:** Single color (teal/blue)

---

### Row C — Country Summary Table

1. **Add visual** → **Table**
2. Dataset: Email Quality Summary
3. **Columns (in order):**
   - COUNTRY
   - TOTAL_COMPANIES
   - WITH_EMAIL
   - MISSING_EMAIL
   - PCT_WITH_EMAIL
   - PCT_MISMATCH (as "Accuracy Mismatch")
   - PCT_SPECIFIC (as "Consistency %")

4. **Sort by:** TOTAL_COMPANIES descending
5. **Title:** `Country Summary`
6. **Format numbers:**
   - TOTAL_COMPANIES: 0 decimals, comma separator
   - WITH_EMAIL: 0 decimals, comma separator
   - MISSING_EMAIL: 0 decimals, comma separator
   - Percentages: 2 decimals

---

## Step 4 — Build Sheet 2: Issues by Country

### Visual 1 — Issues Heat Map

1. **Add visual** → **Pivot table**
2. Dataset: Email Issues Unpivoted
3. **Rows:** `COUNTRY`
4. **Columns:** `ISSUE`
5. **Values:** `affected` (sum)
6. **Color scale:** Green (low) to Red (high)
7. **Title:** `Issues by Country Heatmap`

---

### Visual 2 — Issues Ranking

1. **Add visual** → **Horizontal bar chart**
2. Dataset: Email Issues Unpivoted
3. **Y-axis:** `ISSUE` (sort by `pct_affected` descending)
4. **X-axis:** `pct_affected`
5. **Color by:** `CATEGORY`
   - Coverage: Green
   - Quality: Red
   - Noise: Amber
6. **Title:** `Top Issues (% Affected)`

---

### Visual 3 — Issue Details Table

1. **Add visual** → **Table**
2. Dataset: Email Issues Unpivoted
3. **Columns:**
   - COUNTRY
   - ISSUE
   - CATEGORY
   - affected (as "# Affected")
   - pct_affected (as "% of Total")

4. **Sort by:** affected descending
5. **Title:** `Issue Details by Country`

---

## Step 5 — Build Sheet 3: Trends

### Visual 1 — Dimension Trends (Line Chart)

1. **Add visual** → **Line chart**
2. Dataset: Email Global Summary
3. **X-axis:** `RUN_DATE`
4. **Y-axis (3 lines):**
   - `AVG_COVERAGE_PCT` (line 1, blue)
   - `AVG_ACCURACY_PCT` (line 2, purple)
   - `AVG_CONSISTENCY_PCT` (line 3, green)

5. **Title:** `Coverage + Accuracy + Consistency Trends`

---

### Visual 2 — Overall Quality Score Trend

1. **Add visual** → **Line chart**
2. Dataset: Email Global Summary
3. **X-axis:** `RUN_DATE`
4. **Y-axis:** `OVERALL_QUALITY_SCORE` (navy line, thick)
5. **Title:** `Overall Quality Score Trend`

---

### Visual 3 — What Changed Table

1. **Add visual** → **Table**
2. Dataset: Email Quality Delta
3. **Filter:** `DIRECTION = 'IMPROVED'` (to show only resolved issues)
4. **Columns:**
   - RUN_DATE (as "Week")
   - COUNTRY
   - ISSUE
   - DELTA (as "# Resolved", show absolute value)
   - ROOT_CAUSE
   - SCORE_IMPACT (as "Score Impact (pts)")
   - DIRECTION (as "Status")

5. **Conditional formatting on Status:**
   - "IMPROVED" = Green background
   - "WORSENED" = Red background
   - "NO CHANGE" = Gray background

6. **Sort by:** RUN_DATE descending
7. **Title:** `What Changed (Issues Resolved)`

---

### Visual 4 — Open Issues Table (Optional)

1. **Add visual** → **Table**
2. Dataset: Email Quality Delta
3. **Filter:** `DIRECTION IN ('WORSENED', 'NO CHANGE')` AND latest week only
4. **Columns:**
   - COUNTRY
   - ISSUE
   - CATEGORY
   - CURR_COUNT (as "# Affected")
   - ROOT_CAUSE

5. **Title:** `Open Issues (Still Need Fixing)`

---

## Step 6 — Format & Polish

1. **Set color scheme:** Blue/teal/green accent colors
2. **Add dashboard title:** "Email Data Quality — 13 Markets"
3. **Add date stamp:** Display `RUN_DATE` in the title or footer
4. **Organize layout:**
   - Overview: KPIs top, charts below
   - Issues: Heat map left, details right
   - Trends: Two trend lines top, tables bottom

5. **Test all filters:** Ensure they work across all sheets

---

## Verification Checklist

- [ ] All 4 SPICE datasets created and scheduled
- [ ] 10 KPI cards on Overview sheet
- [ ] Coverage bar chart visible
- [ ] Country summary table shows all 13 markets
- [ ] Issues heat map displays properly
- [ ] Dimension trends chart shows 3 lines
- [ ] Quality score trend is separate
- [ ] What Changed table filters for IMPROVED only
- [ ] All filters (Country, Date, Category) work across sheets
- [ ] Dashboard refreshes Friday 7:30 PM IST

---

## SQL Reference — Verify Data Before Building

Run these checks in Snowflake to verify all tables are populated correctly:

### Check 1 — Global Summary (should return 1 row)
```sql
SELECT TOTAL_DISTINCT_COMPANIES, TOTAL_MARKETS_13, TOTAL_NO_LOCATION, OVERALL_QUALITY_SCORE
FROM BI.DW.DQ_EMAIL_GLOBAL_SUMMARY
ORDER BY RUN_DATE DESC LIMIT 1;
```

Expected: `15118766 | 13812809 | 1107954 | ~38-40`

### Check 2 — Country Summary (should return 13 rows)
```sql
SELECT COUNTRY, TOTAL_COMPANIES, WITH_EMAIL, MISSING_EMAIL, PCT_WITH_EMAIL
FROM BI.DW.DQ_EMAIL_QUALITY_SUMMARY
ORDER BY RUN_DATE DESC, TOTAL_COMPANIES DESC LIMIT 13;
```

Expected: AU ~1.3M, US ~9M, JP ~1.2M, etc.

### Check 3 — Delta Table (might be 0 rows on first run)
```sql
SELECT COUNT(*) AS delta_rows, MAX(RUN_DATE)
FROM BI.DW.DQ_EMAIL_QUALITY_DELTA;
```

Expected: 0 (first run) or 91 (13 countries × 7 issues, if second+ run)

### Check 4 — Issues Unpivoted (custom SQL test)
```sql
SELECT COUNT(*) FROM (
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
);
```

Expected: 91 rows (13 × 7 issues)

---

## Dataset Field Reference

### Email Global Summary
- TOTAL_DISTINCT_COMPANIES (15.1M)
- TOTAL_MARKETS_13 (13.8M)
- TOTAL_NO_LOCATION (1.1M)
- AVG_COVERAGE_PCT
- AVG_ACCURACY_PCT
- AVG_CONSISTENCY_PCT
- OVERALL_QUALITY_SCORE

### Email Quality Summary
- COUNTRY (13 values)
- TOTAL_COMPANIES
- WITH_EMAIL
- MISSING_EMAIL
- PCT_WITH_EMAIL
- HAS_EMAIL_OTHER_MARKET
- UNVERIFIED, UNDELIVERABLE, NOT_CHECKED
- PCT_MISMATCH (accuracy)
- PCT_SPECIFIC (consistency)

### Email Quality Delta
- RUN_DATE
- COUNTRY
- CATEGORY (Coverage / Quality / Noise)
- ISSUE
- PREV_COUNT, CURR_COUNT, DELTA
- DIRECTION (IMPROVED / WORSENED / NO CHANGE)
- ROOT_CAUSE
- SCORE_IMPACT

### Email Issues Unpivoted
- RUN_DATE, COUNTRY
- CATEGORY, ISSUE
- affected (count)
- pct_affected (%)
