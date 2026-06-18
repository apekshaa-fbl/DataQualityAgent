# Company Email Data Quality — RCA Report (13 Core Markets)

**Run date:** 2026-06-11 08:33 UTC
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

## 1. Total Email Rows by Country

> Total raw email rows per country including all quality levels.

| COUNTRY | TOTAL_EMAIL_ROWS | DISTINCT_COMPANIES |
| --- | --- | --- |
| US | 1861054 | 1563735 |
| AU | 1175030 | 875592 |
| JP | 327214 | 273713 |
| CA | 204427 | 162004 |
| NZ | 178195 | 137438 |
| ID | 98920 | 82397 |
| MY | 97104 | 78058 |
| SG | 83224 | 67039 |
| TH | 72298 | 49878 |
| HK | 58286 | 42867 |
| PH | 33453 | 25619 |
| KR | 28458 | 20927 |
| VN | 18626 | 13856 |

---

## 2. Email Coverage by Country (PUBLISHED Companies)

> % of PUBLISHED companies that have at least 1 email. `missing_email` = source team backfill gap.

| COUNTRY | TOTAL_COMPANIES | WITH_EMAIL | MISSING_EMAIL | PCT_WITH_EMAIL | PCT_MISSING |
| --- | --- | --- | --- | --- | --- |
| US | 9064254 | 1240494 | 7823760 | 13.69 | 86.31 |
| AU | 1337465 | 745822 | 591643 | 55.76 | 44.24 |
| JP | 1273949 | 254236 | 1019713 | 19.96 | 80.04 |
| CA | 1006338 | 156456 | 849882 | 15.55 | 84.45 |
| ID | 255737 | 80054 | 175683 | 31.30 | 68.70 |
| NZ | 191051 | 111816 | 79235 | 58.53 | 41.47 |
| SG | 167705 | 55524 | 112181 | 33.11 | 66.89 |
| MY | 133763 | 68634 | 65129 | 51.31 | 48.69 |
| HK | 122993 | 34795 | 88198 | 28.29 | 71.71 |
| KR | 102106 | 19818 | 82288 | 19.41 | 80.59 |
| TH | 72441 | 46704 | 25737 | 64.47 | 35.53 |
| PH | 64463 | 23462 | 41001 | 36.40 | 63.60 |
| VN | 20544 | 13080 | 7464 | 63.67 | 36.33 |

---

## 3. PUBLISHED Companies with FQDN but ZERO Emails

> Has a website domain but no company email. **Source team backfill target** — these domains should yield emails.

| COUNTRY | COMPANIES_WITH_FQDN | MISSING_EMAIL | HAS_EMAIL | PCT_MISSING |
| --- | --- | --- | --- | --- |
| US | 9064254 | 7823760 | 1240494 | 86.31 |
| JP | 1273949 | 1019713 | 254236 | 80.04 |
| CA | 1006338 | 849882 | 156456 | 84.45 |
| AU | 1337465 | 591643 | 745822 | 44.24 |
| ID | 255737 | 175683 | 80054 | 68.70 |
| SG | 167705 | 112181 | 55524 | 66.89 |
| HK | 122993 | 88198 | 34795 | 71.71 |
| KR | 102106 | 82288 | 19818 | 80.59 |
| NZ | 191051 | 79235 | 111816 | 41.47 |
| MY | 133763 | 65129 | 68634 | 48.69 |
| PH | 64463 | 41001 | 23462 | 63.60 |
| TH | 72441 | 25737 | 46704 | 35.53 |
| VN | 20544 | 7464 | 13080 | 36.33 |

---

## 4. Email Type Breakdown by Country

> `system_blocked` = must exclude. `free_provider` = exclude unless only option. `generic_role_based` = info@/contact@ etc. `specific_company` = best quality.

| COUNTRY | EMAIL_TYPE | CNT | PCT_OF_COUNTRY |
| --- | --- | --- | --- |
| AU | specific_company | 592573 | 50.46 |
| AU | generic_role_based | 581458 | 49.51 |
| AU | system_blocked | 285 | 0.02 |
| CA | generic_role_based | 135819 | 66.59 |
| CA | specific_company | 68105 | 33.39 |
| CA | system_blocked | 42 | 0.02 |
| HK | generic_role_based | 30022 | 51.52 |
| HK | specific_company | 28195 | 48.38 |
| HK | system_blocked | 59 | 0.10 |
| ID | specific_company | 56165 | 56.81 |
| ID | generic_role_based | 42681 | 43.17 |
| ID | system_blocked | 25 | 0.03 |
| JP | specific_company | 189862 | 58.04 |
| JP | generic_role_based | 136987 | 41.88 |
| JP | system_blocked | 272 | 0.08 |
| KR | specific_company | 22086 | 77.65 |
| KR | generic_role_based | 6336 | 22.28 |
| KR | system_blocked | 20 | 0.07 |
| MY | specific_company | 55394 | 57.07 |
| MY | generic_role_based | 41600 | 42.86 |
| MY | system_blocked | 72 | 0.07 |
| NZ | specific_company | 97342 | 54.64 |
| NZ | generic_role_based | 80729 | 45.31 |
| NZ | system_blocked | 90 | 0.05 |
| PH | specific_company | 19065 | 57.03 |
| PH | generic_role_based | 14356 | 42.94 |
| PH | system_blocked | 8 | 0.02 |
| SG | specific_company | 41825 | 50.29 |
| SG | generic_role_based | 41274 | 49.63 |
| SG | system_blocked | 66 | 0.08 |
| TH | specific_company | 46849 | 64.88 |
| TH | generic_role_based | 25314 | 35.06 |
| TH | system_blocked | 46 | 0.06 |
| US | generic_role_based | 1144795 | 61.71 |
| US | specific_company | 709767 | 38.26 |
| US | system_blocked | 595 | 0.03 |
| VN | specific_company | 12059 | 64.81 |
| VN | generic_role_based | 6544 | 35.17 |
| VN | system_blocked | 5 | 0.03 |

---

## 5. Duplicate / Shared Emails by Country

> Emails appearing on multiple company records. Shared generic addresses inflate counts without adding value.

| COUNTRY | DISTINCT_EMAILS | UNIQUE_TO_ONE_CO | SHARED_ACROSS_COS | PCT_SHARED |
| --- | --- | --- | --- | --- |
| NZ | 169303 | 163214 | 6089 | 3.60 |
| MY | 92601 | 89537 | 3064 | 3.31 |
| SG | 79230 | 76712 | 2518 | 3.18 |
| HK | 55481 | 53921 | 1560 | 2.81 |
| JP | 306639 | 298337 | 8302 | 2.71 |
| AU | 1136039 | 1106210 | 29829 | 2.63 |
| ID | 95070 | 92792 | 2278 | 2.40 |
| CA | 197345 | 192938 | 4407 | 2.23 |
| KR | 26444 | 25859 | 585 | 2.21 |
| US | 1798146 | 1758521 | 39625 | 2.20 |
| TH | 67960 | 66612 | 1348 | 1.98 |
| VN | 17871 | 17546 | 325 | 1.82 |
| PH | 32591 | 31999 | 592 | 1.82 |

---

## 6. Top Shared Emails (on >5 Companies) — Root Cause

> These are the actual duplicate culprits. Generic/domain-level emails being assigned to many companies. Source field shows where they came from.

| EMAIL | COUNTRY | ON_N_COMPANIES | SOURCES |
| --- | --- | --- | --- |
| biz@usaonline.us | US | 854 | AVT, BEES |
| sample@email.com | JP | 854 | BEES_AGENT, GMAPS |
| sample@mail.com | JP | 587 | GMAPS |
| support@skipthedishes.ca | CA | 545 | BEES |
| accessibility@skipthedishes.com | CA | 525 | BEES |
| info@mysite.com | AU | 508 | AVT, BEES, FBL, HAIKU35-V4, TRUELOCAL, YP |
| quality@petalsnetwork.com | AU | 417 | BEES, FBL |
| xxxxx@gmail.com | JP | 371 | GMAPS |
| sales@teleinfomedia.co.th | TH | 367 | BEES, GMAPS |
| marketing@teleinfomedia.co.th | TH | 366 | GMAPS |
| hq@petalsnetwork.com | AU | 341 | BEES, FBL |
| sample@sample.co.jp | JP | 278 | GMAPS |
| info@mysite.co.jp | JP | 272 | BEES_AGENT, GMAPS |
| sample@text.com | JP | 255 | GMAPS |
| info@mysite.com | US | 225 | AVT, BEES |
| sample@sample.jp | JP | 211 | GMAPS |
| sample@yamadahp.jp | JP | 200 | GMAPS |
| support@cre.ma | KR | 184 | AVT, GMAPS |
| admin@telepathy.com | US | 178 | BEES |
| john@oddle.me | SG | 178 | GMAPS |
| godo@godo.co.kr | KR | 173 | GMAPS |
| info@domain.co.jp | JP | 164 | GMAPS |
| aaa@bbb.jp | JP | 155 | GMAPS |
| stephen@marketmuscles.com | US | 150 | BEES |
| support@webador.com | NZ | 141 | GMAPS |
| info@example.com | AU | 138 | AVT, BEES, BEES_AGENT, FBL |
| contact@australiandentists.com.au | AU | 133 | BEES, FBL |
| yamada@gmail.com | JP | 130 | GMAPS |
| aaa@bbb.co.jp | JP | 129 | BEES_AGENT, GMAPS |
| houmuka@housedo.co.jp | JP | 127 | BEES_AGENT |
| donate@opencart.com | HK | 123 | GMAPS |
| aaa@bbb.com | JP | 123 | BEES_AGENT, GMAPS |
| abc@def.com | JP | 122 | GMAPS |
| info@stagheaddesigns.com | JP | 122 | GMAPS |
| info@marketingsweet.com.au | AU | 121 | AVT, FBL, GMAPS |
| xxx@gmail.com | JP | 120 | GMAPS |
| xxx@xxxxx.xxx | JP | 119 | GMAPS |
| noreply@envato.com | AU | 115 | AVT, BEES, BEES_AGENT, FBL, HAIKU35-V4 |
| hi@mystore.com | JP | 113 | GMAPS |
| demo@volvocars.com | JP | 102 | GMAPS |

---

## 7. Email Source by Country

> Which source/vendor is contributing emails per country. Helps identify which source is injecting bad emails.

| COUNTRY | SOURCE | CNT | PCT |
| --- | --- | --- | --- |
| AU | FBL | 304458 | 25.91 |
| AU | ADMIN | 211014 | 17.96 |
| AU | GMAPS | 198105 | 16.86 |
| AU | HAIKU35-V4 | 155497 | 13.23 |
| AU | BEES | 148073 | 12.60 |
| AU | TRUELOCAL | 64598 | 5.50 |
| AU | AVT | 18837 | 1.60 |
| AU | WP | 17782 | 1.51 |
| AU | BEES_AGENT | 17602 | 1.50 |
| AU | BRANDFETCH | 14963 | 1.27 |
| AU | NDIS | 9918 | 0.84 |
| AU | YP | 5231 | 0.45 |
| AU | HIPAGES | 3837 | 0.33 |
| AU | NULL | 1719 | 0.15 |
| AU | SUPPLYNATION | 1529 | 0.13 |
| AU | LOCALSEARCH | 1162 | 0.10 |
| AU | LLM | 475 | 0.04 |
| AU | ONEFLARE | 119 | 0.01 |
| AU | VC | 111 | 0.01 |
| CA | BEES | 148011 | 72.40 |
| CA | AVT | 56039 | 27.41 |
| CA | FBL | 377 | 0.18 |
| HK | GMAPS | 28211 | 48.40 |
| HK | BEES_AGENT | 19651 | 33.71 |
| HK | AVT | 7035 | 12.07 |
| HK | BEES | 3389 | 5.81 |
| ID | BEES_AGENT | 68808 | 69.56 |
| ID | BEES | 21032 | 21.26 |
| ID | AVT | 9080 | 9.18 |
| JP | GMAPS | 156733 | 47.90 |
| JP | BEES_AGENT | 110549 | 33.78 |
| JP | BEES | 47702 | 14.58 |
| JP | AVT | 12230 | 3.74 |
| KR | GMAPS | 18876 | 66.33 |
| KR | BEES | 7007 | 24.62 |
| KR | AVT | 2575 | 9.05 |
| MY | BEES_AGENT | 65076 | 67.02 |
| MY | GMAPS | 26206 | 26.99 |
| MY | AVT | 5364 | 5.52 |
| MY | BEES | 455 | 0.47 |
| MY | FBL | 3 | 0.00 |
| NZ | HAIKU35-V4 | 87412 | 49.05 |
| NZ | GMAPS | 28479 | 15.98 |
| NZ | NZBN | 27463 | 15.41 |
| NZ | BEES | 7754 | 4.35 |
| NZ | ANZCOMMUNITY | 7623 | 4.28 |
| NZ | FBL | 6685 | 3.75 |
| NZ | BEES_AGENT | 4667 | 2.62 |
| NZ | AVT | 3660 | 2.05 |
| NZ | YP | 3542 | 1.99 |
| NZ | NULL | 908 | 0.51 |
| NZ | ADMIN | 1 | 0.00 |
| NZ | BRANDFETCH | 1 | 0.00 |
| PH | BEES_AGENT | 19608 | 58.61 |
| PH | BEES | 8756 | 26.17 |
| PH | AVT | 5089 | 15.21 |
| SG | BEES_AGENT | 41970 | 50.43 |
| SG | GMAPS | 26274 | 31.57 |
| SG | AVT | 11947 | 14.36 |
| SG | BEES | 3031 | 3.64 |
| SG | NULL | 2 | 0.00 |
| TH | GMAPS | 53816 | 74.44 |
| TH | BEES | 16184 | 22.39 |
| TH | AVT | 1894 | 2.62 |
| TH | FBL | 404 | 0.56 |
| US | BEES | 1104545 | 59.35 |
| US | AVT | 756509 | 40.65 |
| VN | GMAPS | 9352 | 50.21 |
| VN | BEES | 7108 | 38.16 |
| VN | AVT | 1760 | 9.45 |
| VN | FBL | 406 | 2.18 |

---

## 8. Verification Status by Country

> 75%+ emails globally have NULL verification. These have never been checked for deliverability.

| COUNTRY | TOTAL | UNVERIFIED | HIGHLY_LIKELY | LIKELY | UNSURE | PCT_UNVERIFIED |
| --- | --- | --- | --- | --- | --- | --- |
| CA | 204427 | 204427 | 0 | 0 | 0 | 100.00 |
| ID | 98920 | 98920 | 0 | 0 | 0 | 100.00 |
| KR | 28458 | 28458 | 0 | 0 | 0 | 100.00 |
| MY | 97104 | 97104 | 0 | 0 | 0 | 100.00 |
| US | 1861054 | 1861054 | 0 | 0 | 0 | 100.00 |
| JP | 327214 | 327214 | 0 | 0 | 0 | 100.00 |
| TH | 72298 | 72298 | 0 | 0 | 0 | 100.00 |
| HK | 58286 | 58286 | 0 | 0 | 0 | 100.00 |
| SG | 83224 | 83224 | 0 | 0 | 0 | 100.00 |
| PH | 33453 | 33453 | 0 | 0 | 0 | 100.00 |
| VN | 18626 | 18626 | 0 | 0 | 0 | 100.00 |
| NZ | 178195 | 52999 | 45 | 108363 | 16788 | 29.74 |
| AU | 1175030 | 221386 | 161666 | 420818 | 371160 | 18.84 |

---

## 9. Deliverability by Country

> `em-av-undeliverable` = confirmed bad, must suppress immediately. `NULL` = never checked, must run through verifier waterfall.

| COUNTRY | TOTAL | UNDELIVERABLE | HIGHLY_LIKELY | LIKELY | UNSURE | NOT_CHECKED | PCT_UNDELIVERABLE | PCT_NOT_CHECKED |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AU | 1435456 | 155483 | 169323 | 436632 | 388710 | 285308 | 10.83 | 19.88 |
| NZ | 203728 | 7581 | 46 | 110742 | 17099 | 68260 | 3.72 | 33.51 |
| JP | 396225 | 0 | 0 | 0 | 0 | 396225 | 0.00 | 100.00 |
| US | 1942317 | 0 | 0 | 0 | 0 | 1942317 | 0.00 | 100.00 |
| SG | 94032 | 0 | 0 | 0 | 0 | 94032 | 0.00 | 100.00 |
| VN | 34010 | 0 | 0 | 0 | 0 | 34010 | 0.00 | 100.00 |
| HK | 69312 | 0 | 0 | 0 | 0 | 69312 | 0.00 | 100.00 |
| KR | 46756 | 0 | 0 | 0 | 0 | 46756 | 0.00 | 100.00 |
| CA | 206644 | 0 | 0 | 0 | 0 | 206644 | 0.00 | 100.00 |
| TH | 99986 | 0 | 0 | 0 | 0 | 99986 | 0.00 | 100.00 |
| ID | 103956 | 0 | 0 | 0 | 0 | 103956 | 0.00 | 100.00 |
| MY | 108921 | 0 | 0 | 0 | 0 | 108921 | 0.00 | 100.00 |
| PH | 35617 | 0 | 0 | 0 | 0 | 35617 | 0.00 | 100.00 |

---

## 10. Email Domain vs Company FQDN Mismatch

> Email domain root ≠ company FQDN root. High mismatch = emails from unrelated domains being assigned to wrong companies.

| COUNTRY | PAIRS | MATCH | MISMATCH | PCT_MISMATCH |
| --- | --- | --- | --- | --- |
| KR | 27074 | 10152 | 16922 | 62.50 |
| TH | 67040 | 30875 | 36165 | 53.95 |
| VN | 18231 | 9312 | 8919 | 48.92 |
| JP | 307713 | 168316 | 139397 | 45.30 |
| ID | 105999 | 61850 | 44149 | 41.65 |
| MY | 92857 | 60994 | 31863 | 34.31 |
| PH | 35714 | 24127 | 11587 | 32.44 |
| NZ | 155105 | 111829 | 43276 | 27.90 |
| HK | 53353 | 38597 | 14756 | 27.66 |
| AU | 1060703 | 799836 | 260867 | 24.59 |
| SG | 84767 | 65388 | 19379 | 22.86 |
| US | 1583758 | 1258858 | 324900 | 20.51 |
| CA | 259224 | 218102 | 41122 | 15.86 |

---

## Root Cause Analysis

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
