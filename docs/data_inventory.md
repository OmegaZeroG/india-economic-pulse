# Data inventory

Status as of 20 Oct 2026 (Week 1, Day 1 probe from a Windows machine with `requests`). Nothing is downloaded yet; this records what is reachable.

| Source | Link | Frequency | First month available | Units | Release lag | File format | Known problems / access status |
|---|---|---|---|---|---|---|---|
| UPI (NPCI) | https://www.npci.org.in/what-we-do/upi/product-statistics | monthly | TBD | volume: millions; value: Rs crore | ~1 day after month end | HTML table | **Scripted requests get HTTP 403.** Fallback per plan: India Data Portal copy or RBI/NPCI monthly PDFs, or manual download logged with date. |
| Fuel (PPAC) | https://ppac.gov.in/consumption/products-wise | monthly | TBD | thousand metric tonnes | ~1 month | Excel (`...PT_Consumption_English.xls`) | Page loads (200) but its table is filled by JavaScript, and the direct .xls link redirects to an internal address (login-gated). Page also references AJAX endpoints `AjaxController/getConsumptionPetroleumProductsData`. Provisional months get revised. |
| GST (GST portal) | https://www.gst.gov.in/download/gststatistics | monthly | TBD | Rs crore | ~1st of next month | PDF + Excel | **Portal's firewall rejects scripted requests** ("Request Rejected") after the first hit. Plan: manual download of the files, parsed by script. |
| IIP (MoSPI) | https://api.mospi.gov.in/api/iip/ | monthly | 2023 on base 2022-23 | index, YoY % | ~28th of following month | JSON API | **No key needed (confirmed).** Base years offered: 2022-23, 2011-12, 2004-05, 1993-94. New base 2022-23 has data for years 2023-2026 only, about 40 monthly points. The server needs a legacy-SSL workaround (`OP_LEGACY_SERVER_CONNECT`). Data endpoint: `/api/iip/getIipData` (paginated). Ingested by `src/ingest/iip.py`: 41 months, Apr 2023 to Aug 2026, no gaps. Latest Aug 2026 = 8.0% YoY. `release_date` is the date we pulled the value, not MoSPI's official release date. |
| GDP (MoSPI) | https://esankhyiki.mospi.gov.in/macroindicators?product=nas | quarterly | TBD | YoY % | ~60 days after quarter end | JSON API / web | Not yet tested. |
| E-way bills (optional) | | | | | | | Not yet checked. |
| Electricity (optional) | | | | | | | Not yet checked. |

## Decision pending: IIP base year
MoSPI has rebased IIP to 2022-23. The old 2011-12 series is long, the new one short. Plan wants one consistent series; choose in Week 1 and log it in `data_quality_log.md`.
