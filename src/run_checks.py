"""Run the five SQL checks in sql/checks.sql against data/pulse.db.

Prints PASS/FAIL per check and appends any failure to docs/data_quality_log.md.
Exit code is the number of failed checks (0 = all pass).

Usage:  python src/run_checks.py
"""
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ingest"))
from common import ROOT, log_issue  # noqa: E402

DB = ROOT / "data" / "pulse.db"
CHECKS = ROOT / "sql" / "checks.sql"


def run() -> int:
    text = CHECKS.read_text(encoding="utf-8")
    blocks = re.split(r"^-- CHECK ", text, flags=re.M)[1:]
    con = sqlite3.connect(DB)
    failed = 0
    for b in blocks:
        head, _, query = b.partition("\n")
        name, _, why = head.partition(":")
        n = con.execute(query).fetchone()[0]
        status = "PASS" if n == 0 else "FAIL"
        print(f"  [{status}] {name.strip():<30} {why.strip()}" + ("" if n == 0 else f"  ({n} rows)"))
        if n:
            failed += 1
            log_issue("SQL check", f"{name.strip()} failed: {n} rows ({why.strip()})",
                      "investigate before using the data", str(n))
    con.close()
    print(f"{len(blocks) - failed}/{len(blocks)} checks passed")
    return failed


if __name__ == "__main__":
    sys.exit(run())
