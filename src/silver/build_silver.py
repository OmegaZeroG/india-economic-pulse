"""SILVER: rebuild every silver table from bronze. Each table is emptied and refilled, so silver is always exactly
what bronze says, parsed by the code in this folder.

Run after src/bronze/load_bronze.py.  Usage:  python src/silver/build_silver.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import connect, run_sql_file  # noqa: E402

import ewaybill, gdp, gst, iip, ppac, upi  # noqa: E402,F401  (sibling modules, one per source)


def main() -> None:
    con = connect()
    run_sql_file(con, "silver_schema.sql")
    for module in (upi, ppac, gst, ewaybill, iip, gdp):
        module.build(con)
        con.commit()
    con.close()


if __name__ == "__main__":
    main()
