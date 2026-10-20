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
    """Append one line to docs/data_quality_log.md."""
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"| {today()} | {source} | {issue} | {action} | {rows} |\n")


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
