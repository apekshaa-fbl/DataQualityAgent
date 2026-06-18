# QuickSight Setup Guide — CTA Dashboard

---

## 1. Connect Snowflake to QuickSight

1. Go to **QuickSight → Manage Data → New Dataset → Snowflake**
2. Enter connection details:
   - Account: `SYPBXPR-CZ72457`
   - Database: `BI`
   - Schema: `DW`
   - Username / Password: same as pipeline `.env`
3. Name the connection `CTA_Snowflake`
4. Click **Validate Connection** → **Create data source**

---

## 2. Add the Three Datasets

Create one dataset per table. For each:
**New Dataset → Snowflake → CTA_Snowflake → BI → DW → select table → Import to SPICE**

| Dataset name       | Table                        | Refresh schedule |
|--------------------|------------------------------|------------------|
| `CTA Staging`      | `BI.DW.CTA_staging`          | Daily            |
| `CTA By Status`    | `BI.DW.CTA_summary_by_status`| Daily            |
| `CTA Monitoring`   | `BI.DW.CTA_monitoring`       | Daily            |

---

## 3. Date Hierarchy (apply to all three datasets)

In the dataset editor, for each date-related field set the hierarchy:

| Field           | Type    | Use as            |
|-----------------|---------|-------------------|
| `run_date`      | Date    | Filter / X-axis   |
| `run_year`      | Integer | Filter / Group by |
| `run_quarter`   | String  | Filter / Group by |
| `run_month`     | Integer | Filter / Group by |
| `run_month_name`| String  | Label             |

> In QuickSight, create a **Date Hierarchy**: run_year → run_quarter → run_month → run_date
> This lets you drill down from year to day on any visual.

---

## 4. Dashboard Layout

### Page 1 — Overview (uses `CTA Monitoring`)

| Visual | Type | Fields |
|--------|------|--------|
| Total Customers | KPI card | `total_customers` (SUM) |
| Total Markets | KPI card | `total_markets` (MAX) |
| In Firmable | KPI card | `in_firmable_count` (SUM) |
| Not in Firmable | KPI card | `not_in_firmable_count` (SUM) |
| In Firmable % | KPI card | `in_firmable_pct` (AVG) |
| Avg Field Coverage | KPI card | `avg_field_coverage_pct` (AVG) |
| Customers over time | Line chart | X: `run_date`, Y: `total_customers` |
| In FBL % over time | Line chart | X: `run_date`, Y: `in_firmable_pct` |
| Coverage % over time | Line chart | X: `run_date`, Y: `avg_field_coverage_pct` |

**Filters to add (top of page):**
- `run_year` — dropdown
- `run_quarter` — dropdown
- `run_month` — dropdown
- `run_date` — date range picker

---

### Page 2 — Field Coverage (uses `CTA Monitoring`)

| Visual | Type | Fields |
|--------|------|--------|
| Coverage by field | Horizontal bar | Fields: all 9 `*_coverage_pct` columns |
| Coverage heatmap over time | Pivot table | Rows: `run_month_name`, Cols: field names, Values: avg coverage % |

**9 fields to show:**
- `name_coverage_pct`
- `website_coverage_pct`
- `linkedin_coverage_pct`
- `industry_coverage_pct`
- `founded_year_coverage_pct`
- `hq_country_coverage_pct`
- `employee_count_coverage_pct`
- `phone_coverage_pct`
- `email_coverage_pct`

---

### Page 3 — Summary by Status (uses `CTA By Status`)

| Visual | Type | Fields |
|--------|------|--------|
| Customers by status | Donut chart | Group: `sub_status`, Value: `total_customers` |
| In FBL by status | Grouped bar | X: `sub_status`, Y: `in_firmable_count` vs `not_in_firmable_count` |
| Coverage by status | Pivot table | Rows: `sub_status`, Cols: field coverage columns, Values: avg % |
| Status trend | Line chart | X: `run_date`, Y: `total_customers`, Color: `sub_status` |

---

### Page 4 — Monitoring Table (uses `CTA Monitoring`)

Add a **Table visual** with all columns:

```
run_date | run_year | run_quarter | run_month_name
total_customers | total_markets | in_firmable_count | not_in_firmable_count | in_firmable_pct
name_coverage_pct | website_coverage_pct | linkedin_coverage_pct | industry_coverage_pct
founded_year_coverage_pct | hq_country_coverage_pct | employee_count_coverage_pct
phone_coverage_pct | email_coverage_pct | avg_field_coverage_pct
```

Sort by `run_date DESC` by default.

Add conditional formatting:
- `avg_field_coverage_pct` < 50 → red
- `avg_field_coverage_pct` 50–75 → amber
- `avg_field_coverage_pct` > 75 → green

---

## 5. Global Filters (apply to all pages)

In **Filter pane**, add sheet-level filters linked across pages:

| Filter | Field | Control type |
|--------|-------|--------------|
| Year | `run_year` | Dropdown |
| Quarter | `run_quarter` | Dropdown |
| Month | `run_month_name` | Dropdown |
| Date range | `run_date` | Date range picker |

---

## 6. SPICE Refresh Schedule

1. Go to **Datasets → CTA Monitoring → Schedule refresh**
2. Set to **Daily at 08:00 AEST**
3. Repeat for `CTA Staging` and `CTA By Status`

---

## 7. Validate Data in Snowflake Before Publishing

```sql
-- Check all dates loaded
SELECT run_date, total_customers, in_firmable_count, avg_field_coverage_pct
FROM BI.DW.CTA_monitoring
ORDER BY run_date DESC
LIMIT 20;

-- Check coverage by status
SELECT run_date, sub_status, total_customers, avg_field_coverage_pct
FROM BI.DW.CTA_summary_by_status
ORDER BY run_date DESC, total_customers DESC
LIMIT 30;

-- Check staging has no duplicates
SELECT run_date, COUNT(*), COUNT(DISTINCT cta_id)
FROM BI.DW.CTA_staging
GROUP BY run_date
HAVING COUNT(*) != COUNT(DISTINCT cta_id);
-- Should return 0 rows
```
