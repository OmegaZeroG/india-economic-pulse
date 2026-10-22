"""Rebuild the whole project from the raw files with one command, layer by layer.

  bronze  load every file in data/raw into the database as it arrived (nothing cleaned)
  silver  parse bronze into cleaned, typed tables that record which file each row came from
  gold    build the star schema (dim_date, fact tables, growth views) from silver with SQL, then run the checks
  analysis  index, lag tests and backtest, written back to the database and docs/results

  python src/run_all.py            rebuild from the files already in data/raw (no network needed)
  python src/run_all.py --api      also pull the latest IIP and GDP from MoSPI's open API first

Stops at the first failing step. Refreshing is manual: UPI, PPAC and GST sites block scripts, so new months are
downloaded by hand into data/raw (dated file names) and this command is re-run. Nothing updates by itself.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_STEPS = ["src/bronze/fetch_api.py"]
STEPS = ["src/bronze/load_bronze.py", "src/silver/build_silver.py", "src/gold/build_gold.py",
         "src/analysis/run_week3.py"]


def main() -> int:
    steps = (API_STEPS if "--api" in sys.argv else []) + STEPS
    for step in steps:
        print(f"\n=== {step}", flush=True)
        t = time.time()
        if subprocess.run([sys.executable, step], cwd=ROOT).returncode != 0:
            print(f"FAILED: {step}")
            return 1
        print(f"--- done in {time.time() - t:.0f}s")
    print("\nAll steps finished. Results: data/pulse.db, docs/results/, notebooks/03_index_and_backtest.ipynb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
