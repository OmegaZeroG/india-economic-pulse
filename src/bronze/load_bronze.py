"""BRONZE: load every raw file in data/raw into the database exactly as it arrived. Nothing is cleaned here.

* Spreadsheets (xlsx, xls, and Excel files saved as .csv) become one row per non-empty cell: sheet, row, column,
  the kind of value it held (number, date, text) and the value itself. Numbers keep full precision.
* Text CSV files become cells too (every value as text).
* JSON API pulls become one row per record.
* The file type is detected from the file's first bytes, not its extension.
* A file is skipped if a file of that name with the same SHA-256 hash is already loaded; if the content changed
  under the same name it is reloaded and the change logged; bronze files whose raw file was removed are dropped.

Every file keeps its name, the download date from the name, size, hash and load time in bronze_files, so any
silver row can be traced back to the exact bytes it came from.

Usage:  python src/bronze/load_bronze.py
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW, connect, log_issue, run_sql_file  # noqa: E402

# file-name prefix -> source (longest prefix first)
PREFIXES = [("gst_national_", "gst_national"), ("gst_state_", "gst_state"), ("ewaybill_", "ewaybill"),
            ("upi_", "upi"), ("ppac_", "ppac"), ("iip_", "iip"), ("gdp_", "gdp")]


def classify(name: str) -> str | None:
    return next((src for pre, src in PREFIXES if name.startswith(pre)), None)


def detect_type(path: Path) -> str:
    head = path.read_bytes()[:8]
    if head[:2] == b"PK":
        return "xlsx"
    if head[:4] == bytes([0xD0, 0xCF, 0x11, 0xE0]):
        return "xls"
    if head.lstrip()[:1] in (b"[", b"{"):
        return "json"
    return "csv"


def _cell(v):
    """(cell_type, value_text) for one cell, or None for a blank."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, (pd.Timestamp, datetime, np.datetime64)):
        return "date", str(pd.Timestamp(v))
    if isinstance(v, (bool, np.bool_)):
        return "str", str(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return "num", repr(float(v))
    return "str", str(v)


def spreadsheet_cells(path: Path, ftype: str):
    if ftype == "csv":
        for enc in ("utf-8-sig", "cp1252"):
            try:
                book = {"csv": pd.read_csv(path, header=None, dtype=str, encoding=enc, keep_default_na=False)}
                break
            except UnicodeDecodeError:
                continue
    else:
        book = pd.read_excel(path, header=None, sheet_name=None, dtype=object)
    for sheet_no, (sheet, df) in enumerate(book.items()):
        for (r, c), v in np.ndenumerate(df.to_numpy(dtype=object)):
            cell = _cell(v)
            if cell:
                yield sheet_no, str(sheet), int(r), int(c), cell[0], cell[1]


def drop_file(con, file_id: int) -> None:
    con.execute("DELETE FROM bronze_cells WHERE file_id = ?", (file_id,))
    con.execute("DELETE FROM bronze_api WHERE file_id = ?", (file_id,))
    con.execute("DELETE FROM bronze_files WHERE file_id = ?", (file_id,))


def main() -> None:
    con = connect()
    run_sql_file(con, "bronze_schema.sql")
    on_disk = {p.name: p for p in sorted(RAW.iterdir()) if p.is_file() and classify(p.name)}
    skipped_other = [p.name for p in RAW.iterdir() if p.is_file() and not classify(p.name) and p.name != ".gitkeep"]
    for n in skipped_other:
        print(f"  not a known source, ignored: {n}")

    # bronze files whose raw file is gone
    for fid, name in con.execute("SELECT file_id, file_name FROM bronze_files").fetchall():
        if name not in on_disk:
            drop_file(con, fid)
            print(f"  removed from bronze (raw file no longer in data/raw): {name}")

    loaded = skipped = reloaded = 0
    for name, path in on_disk.items():
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        row = con.execute("SELECT file_id, sha256 FROM bronze_files WHERE file_name = ?", (name,)).fetchone()
        if row and row[1] == sha:
            skipped += 1
            continue
        if row:
            drop_file(con, row[0])
            reloaded += 1
            log_issue("Bronze", f"{name} changed since it was first loaded", "reloaded from the new bytes", "1 file")
        ftype = detect_type(path)
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", name)
        cur = con.execute(
            "INSERT INTO bronze_files (source, file_name, file_date, file_type, sha256, size_bytes, n_records, loaded_at) "
            "VALUES (?,?,?,?,?,?,0,?)", (classify(name), name, dates[-1] if dates else None, ftype, sha,
                                         path.stat().st_size, datetime.now().isoformat(timespec="seconds")))
        fid = cur.lastrowid
        if ftype == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            records = data if isinstance(data, list) else [data]
            con.executemany("INSERT INTO bronze_api VALUES (?,?,?)",
                            [(fid, i, json.dumps(r, ensure_ascii=False)) for i, r in enumerate(records)])
            n = len(records)
        else:
            cells = [(fid, *c) for c in spreadsheet_cells(path, ftype)]
            con.executemany("INSERT INTO bronze_cells VALUES (?,?,?,?,?,?,?)", cells)
            n = len(cells)
        con.execute("UPDATE bronze_files SET n_records = ? WHERE file_id = ?", (n, fid))
        loaded += 1
        print(f"  loaded {name:<44} {ftype:<5}{n:>8,} records")
    con.commit()
    total = con.execute("SELECT COUNT(*), COALESCE(SUM(n_records), 0) FROM bronze_files").fetchone()
    print(f"bronze: {loaded} loaded, {reloaded} reloaded, {skipped} unchanged; {total[0]} files, {total[1]:,} records in all")
    con.close()


if __name__ == "__main__":
    main()
