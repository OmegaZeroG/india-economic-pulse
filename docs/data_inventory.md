# Data inventory

Status as of 20 Oct 2026 (Week 1, Day 1 probe from a Windows machine with `requests`). Nothing is downloaded yet; this records what is reachable.

| Source | Link | Frequency | First month available | Units | Release lag | File format | Known problems / access status |
|---|---|---|---|---|---|---|---|
| UPI (NPCI) | https://www.npci.org.in/what-we-do/upi/product-statistics | monthly | Apr 2023 (loaded; FY2023-24 onward) | volume: millions; value: Rs crore | ~1 day after month end (Sep 2026 already out) | Excel via Download button, one file per financial year | Scripts get HTTP 403, so manual download. 42 months loaded (Apr 2023-Sep 2026), no gaps. Excludes same-account transactions from Aug 2018. UPI growth reflects adoption as well as activity. |
| Fuel (PPAC) | https://ppac.gov.in/consumption/products-wise | monthly | Apr 2000 (loaded, 5 products) | thousand metric tonnes | ~1 week into next month (Sep 2026 out 06.10.2026) | Excel: Historical Report (sheet per FY) + Current Report | Manual download. 318 months, no gaps. Latest months provisional and revised; Aug-Sep 2026 private imports prorated. |
| GST (GST portal) | https://www.gst.gov.in/download/gststatistics | monthly | Apr 2023 (loaded) | Rs crore | ~1st of next month; Aug 2026 is latest | Excel via download icons: state-wise file per FY + one national file | Portal firewall blocks scripts, so manual download. 41 months, no gaps. National file has cess; state files drop cess after FY2024-25. Compensation cess is zero from Apr 2026, so gross incl. cess has a break in Mar-Apr 2026 (use ex-cess for growth). 39 states/UTs; code 99 labelled CBIC in FY2023-24, OIDAR later. Figures are provisional. |
| IIP (MoSPI) | https://api.mospi.gov.in/api/iip/ | monthly | 2023 on base 2022-23 | index, YoY % | ~28th of following month | JSON API | **No key needed (confirmed).** Base years offered: 2022-23, 2011-12, 2004-05, 1993-94. New base 2022-23 has data for years 2023-2026 only, about 40 monthly points. The server needs a legacy-SSL workaround (`OP_LEGACY_SERVER_CONNECT`). Data endpoint: `/api/iip/getIipData` (paginated). Ingested by `src/ingest/iip.py`: 41 months, Apr 2023 to Aug 2026, no gaps. Latest Aug 2026 = 8.0% YoY. `release_date` is the date we pulled the value, not MoSPI's official release date. |
| GDP (MoSPI) | https://esankhyiki.mospi.gov.in/macroindicators?product=nas | quarterly | TBD | YoY % | ~60 days after quarter end | JSON API / web | Not yet tested. |
| E-way bills (optional) | https://www.gst.gov.in/download/gststatistics (E-Way Bill column) | monthly | Apr 2023 (loaded; portal has Apr 2018 on) | count of bills; value in Rs crore | Aug 2026 is latest | Excel, one per FY | **Usable: kept in scope.** 41 months, 38 states, within-state / outgoing / incoming. Outgoing vs incoming counts differ by up to 0.7%. |
| Electricity (optional) | | | | | | | Not yet checked. |

## IIP base year (decided 23 Oct 2026)
Main series: base 2022-23 (41 months, still updated). Robustness check: base 2011-12 (168 months, ends Mar 2026). The two are never spliced: their growth rates correlate only 0.40 over the 36 overlapping months. See `data_quality_log.md`.
