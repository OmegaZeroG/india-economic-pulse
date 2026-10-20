# Data-quality log

Every gap, fix and revision, in date order.

| Date | Source | Issue | Action | Rows affected |
|---|---|---|---|---|
| 2026-10-20 | MoSPI IIP | API rebased: base year 2022-23 now listed, data from 2023 only | Decision pending (see data_inventory.md) | n/a |
| 2026-10-20 | MoSPI API | TLS handshake fails on Python 3.13 (legacy renegotiation) | Use session adapter with `OP_LEGACY_SERVER_CONNECT` for api.mospi.gov.in only | n/a |
| 2026-10-20 | NPCI | HTTP 403 for scripted requests | Use fallback source or logged manual download | n/a |
| 2026-10-20 | GST portal | Firewall rejects scripted requests | Manual download, parse by script | n/a |
| 2026-10-21 | PPAC | latest months are provisional and get revised | re-download each month, upsert | 1590 |
| 2026-10-21 | UPI (NPCI) | Files saved as `.csv` are really Excel (.xlsx) workbooks | `read_any()` in common.py detects type from file bytes | 4 files |
| 2026-10-21 | UPI (NPCI) | Values use Indian digit grouping (29,87,880.49) and month as "July-2026" | Strip commas, parse month text, key on first of month | 42 |
| 2026-10-21 | UPI (NPCI) | Check against plan: Jul 2026 = 23,658.35 mn / Rs 29,87,880.49 cr = 23.66 bn, Rs 29.88 lakh cr | Matches; no action | 1 |
| 2026-10-21 | PPAC | Workbook has one sheet per fiscal year (not one wide table); `.xls` current report is really .xlsx | Parser loops over sheets, fiscal year read from "Period" cell | 1590 |
| 2026-10-21 | PPAC | Apr 2026-Sep 2026 provisional ("as on 06.10.2026"), Aug-Sep 2026 private imports prorated | Current report loaded last so it overrides; re-download monthly | 30 |
| 2026-10-21 | PPAC | Check: Sep 2026 diesel 7,163.6 vs Sep 2025 6,786.1 = +5.6% YoY, equals PPAC's own note | Matches; no action | 1 |
| 2026-10-21 | E-way bill | outgoing vs incoming bill counts differ by up to 0.7% in a month | kept both; national total uses within-state + outgoing only | 41 |
| 2026-10-21 | GST | State workbooks FY2023-24 and FY2024-25 have a CESS column (5-column month blocks); FY2025-26 on do not | Parser reads column names from the sub-header instead of fixed positions; first attempt mis-read the wrong columns and was caught by the cross-check against the national file | 2 files |
| 2026-10-21 | GST | State figures exclude cess, national includes it (state files stopped publishing cess after FY2024-25) | State series defined ex-cess; national keeps cess in its own column | 1594 state rows |
| 2026-10-21 | GST | Compensation cess is zero from Apr 2026 (last non-zero month Mar 2026), so gross incl. cess has a break | Use cgst+sgst+igst for growth comparisons; documented here | 5 months |
| 2026-10-21 | GST | State code 99 named CBIC in FY2023-24, OIDAR afterwards; codes 25/26 (Daman and Diu, Dadra and Nagar Haveli) disappear in FY2026-27 | Name taken by state code from the latest file; missing months left as gaps, not filled | 67 refund cells blank |
| 2026-10-21 | GST | National sheet Jan-25 has a different layout (extra Daily column) | Parser detects it and uses the MTD columns | 1 sheet |
| 2026-10-21 | GST | Checks: state rows vs All-India domestic, national vs state workbook gross (ex-cess), gross - refunds = net | 123 comparisons, 0 outside 0.5% | 41 months |
| 2026-10-21 | E-way bill | Usable monthly file found, 41 months Apr 2023 - Aug 2026 | Kept in scope; national total = within-state + outgoing | 1558 state rows |
| 2026-10-21 | IIP | **Decision: 2022-23 base is the main target series** (41 months, Apr 2023-Aug 2026, still updated; the Oct 2026 forecast is scored against it). 2011-12 base kept as a robustness check only | Both stored in iip_versions.csv, separated by base_year; never spliced | 41 + 168 |
| 2026-10-21 | IIP | 2011-12 series has 168 months (Apr 2012-Mar 2026) but stops at Mar 2026 after the rebase | Used only for longer-history robustness tests, ends Mar 2026 | 168 |
| 2026-10-21 | IIP | Overlap of the two bases (36 months, Apr 2023-Mar 2026): YoY growth correlation 0.40, mean absolute difference 2.3 points, so the rebase changed growth materially | Do not chain the series; report results on both bases separately | 36 |
| 2026-10-21 | GDP (MoSPI) | API publishes GDP levels (constant and current price), not growth; 17 quarters Q1 FY2022-23 to Q1 FY2026-27 | YoY growth computed from constant-price level vs same quarter a year earlier; first four quarters have no growth. Q1 FY2026-27 = 7.82%, the benchmark for the Q2 above/below call | 17 |
| 2026-10-21 | GST | National sheet Dec-25 is missing its "A.1. Domestic" heading | Domestic block located from the first CGST row | 1 sheet |
| 2026-10-21 | GST | Added ex-cess national columns (domestic, gross, refunds, net) so growth is not distorted by the end of compensation cess | `*_ex_cess_cr` columns in fact_gst_national; gross - refunds = net to 0.0% | 41 |
| 2026-10-21 | dim_date | Diwali-month flag is typed in from the published festival calendar; 2024 is an edge case (31 Oct / 1 Nov) and is flagged October | Verify against a calendar cited in the README before Week 3 | 16 years |
| 2026-10-21 | SQL | Five checks in sql/checks.sql all pass on the full load; each was also shown to fail on deliberately broken data (gap, negative, state total, extra row, growth spike) | none needed | 5 checks |
| 2026-10-21 | SQL | Update path tested: re-running load_db.py changes no row counts; adding one new month twice gives exactly one new row | none needed | 1 |
| 2026-10-21 | SQL | Fuel history starts Apr 2000 and includes COVID months (Apr-Jun 2020, flagged in dim_date); growth-plausibility check only covers the project window from Apr 2023 | none needed | 3 months |
