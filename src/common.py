"""Helpers shared by every layer: paths, database access, dated raw-file names, the data-quality log, and the
functions that read bronze back as sheets or records.

Layers (all in data/pulse.db, one table prefix each):
  bronze_*  raw files exactly as they arrived (cell by cell, or JSON records), plus file name, date and hash
  silver_*  cleaned, typed, conformed tables, every row carrying the file it came from
  dim_* / fact_* / v_*  gold: the star schema, growth views and analysis outputs used for reporting
"""
import sqlite3
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "pulse.db"
SQL = ROOT / "sql"
LOG = ROOT / "docs" / "data_quality_log.md"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


# --------------------------------------------------------------------------- small helpers
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


# --------------------------------------------------------------------------- database
def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def run_sql_file(con: sqlite3.Connection, name: str) -> None:
    con.executescript((SQL / name).read_text(encoding="utf-8"))


def replace_table(con: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    """Silver and gold tables are rebuilt from the layer below: empty the table, then insert every row.

    Column names must match the table's; NaN becomes NULL (missing values are never filled).
    """
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    use = [c for c in cols if c in df.columns]
    missing = [c for c in df.columns if c not in cols]
    if missing:
        raise ValueError(f"{table} has no column(s) {missing}")
    con.execute(f"DELETE FROM {table}")
    rows = df[use].astype(object).where(df[use].notna(), None).values.tolist()
    con.executemany(f"INSERT INTO {table} ({', '.join(use)}) VALUES ({', '.join('?' * len(use))})", rows)
    return len(rows)


# --------------------------------------------------------------------------- reading bronze back
def bronze_files(con: sqlite3.Connection, source: str) -> list[tuple[int, str, str]]:
    """(file_id, file_name, file_date) of every bronze file of a source, in file-name order."""
    return con.execute("SELECT file_id, file_name, file_date FROM bronze_files WHERE source = ? ORDER BY file_name",
                       (source,)).fetchall()


def bronze_sheets(con: sqlite3.Connection, file_id: int) -> dict[str, pd.DataFrame]:
    """Rebuild every sheet of a bronze file as a DataFrame with no header row (like read_excel(header=None)).

    Numbers come back as floats, dates as Timestamps, text as text, blanks as NaN.
    """
    cells = pd.read_sql("SELECT sheet_no, sheet, row_num, col_num, cell_type, value_text FROM bronze_cells "
                        "WHERE file_id = ? ORDER BY sheet_no, row_num, col_num", con, params=(file_id,))
    out = {}
    for (_, sheet), g in cells.groupby(["sheet_no", "sheet"], sort=True):
        arr = np.full((int(g["row_num"].max()) + 1, int(g["col_num"].max()) + 1), np.nan, dtype=object)
        for r, c, t, v in zip(g["row_num"], g["col_num"], g["cell_type"], g["value_text"]):
            arr[r, c] = float(v) if t == "num" else pd.Timestamp(v) if t == "date" else v
        out[sheet] = pd.DataFrame(arr)
    return out


def bronze_records(con: sqlite3.Connection, file_id: int) -> list[dict]:
    """The JSON records of a bronze API file, in their original order."""
    import json
    return [json.loads(p) for (p,) in con.execute(
        "SELECT payload FROM bronze_api WHERE file_id = ? ORDER BY record_no", (file_id,))]
