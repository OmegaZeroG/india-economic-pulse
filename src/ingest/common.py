"""Shared helpers: repo paths, dated raw-file names, month-key and logging utilities."""
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
LOG = ROOT / "docs" / "data_quality_log.md"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def today() -> str:
    return date.today().isoformat()


def raw_name(source: str, suffix: str) -> Path:
    """Raw files carry the download date: e.g. iip_2022-23_2026-10-20.json."""
    RAW.mkdir(parents=True, exist_ok=True)
    return RAW / f"{source}_{today()}{suffix}"


def month_key(year: int, month: int) -> pd.Timestamp:
    """First day of month is the date key for every table."""
    return pd.Timestamp(year=int(year), month=int(month), day=1)


def log_issue(source: str, issue: str, action: str, rows: str = "") -> None:
    """Append one line to docs/data_quality_log.md, unless the same issue is already logged.

    Loaders run every month, so an identical source/issue/action is written once, not once per run.
    """
    tail = f"| {source} | {issue} | {action} | {rows} |"
    if LOG.exists() and tail in LOG.read_text(encoding="utf-8"):
        return
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"| {today()} {tail}\n")


def upsert(new: pd.DataFrame, path: Path, key: list[str]) -> int:
    """Merge `new` into the CSV at `path`, replacing rows with the same key.

    Returns the number of rows in the file afterwards. Safe to re-run: no duplicates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        combined = pd.concat([old, new.astype(old.dtypes.to_dict(), errors="ignore")])
    else:
        combined = new
    combined = (combined.drop_duplicates(subset=key, keep="last")
                .sort_values(key).reset_index(drop=True))
    combined.to_csv(path, index=False)
    return len(combined)


def read_any(path, **kw) -> pd.DataFrame:
    """Read a downloaded table whatever its extension says.

    Portals often save Excel files as .csv (or .xlsx as .xls), so sniff the
    file's first bytes: ZIP = xlsx, OLE2 = xls, otherwise text CSV.
    """
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:2] == b"PK" or head[:4] == bytes([0xD0, 0xCF, 0x11, 0xE0]):
        return pd.read_excel(path, **kw)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")
