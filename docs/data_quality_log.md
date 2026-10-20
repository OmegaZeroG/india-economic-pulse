# Data-quality log

Every gap, fix and revision, in date order.

| Date | Source | Issue | Action | Rows affected |
|---|---|---|---|---|
| 2026-10-20 | MoSPI IIP | API rebased: base year 2022-23 now listed, data from 2023 only | Decision pending (see data_inventory.md) | n/a |
| 2026-10-20 | MoSPI API | TLS handshake fails on Python 3.13 (legacy renegotiation) | Use session adapter with `OP_LEGACY_SERVER_CONNECT` for api.mospi.gov.in only | n/a |
| 2026-10-20 | NPCI | HTTP 403 for scripted requests | Use fallback source or logged manual download | n/a |
| 2026-10-20 | GST portal | Firewall rejects scripted requests | Manual download, parse by script | n/a |
