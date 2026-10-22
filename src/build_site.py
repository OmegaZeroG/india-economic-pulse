"""Build the public web dashboard (docs/index.html) for GitHub Pages.

Reads the small data files in powerbi/dashboard_data (made by src/export_dashboard.py from the gold tables), embeds
them in src/site/template.html and writes one self-contained page, docs/index.html, plus docs/.nojekyll so GitHub
Pages serves the repository's docs folder as it is. The page draws its charts with d3 loaded from cdnjs.

  python src/export_dashboard.py     refresh the data files from the database
  python src/build_site.py           rebuild docs/index.html

Publish: GitHub repository > Settings > Pages > Deploy from a branch > main > /docs.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "powerbi" / "dashboard_data"
TEMPLATE = ROOT / "src" / "site" / "template.html"
OUT = ROOT / "docs" / "index.html"
FILES = ["index_monthly", "growth", "gst_state", "backtest_results", "backtest_summary", "robustness", "correlations"]


def main() -> None:
    data = {}
    for name in FILES:
        df = pd.read_csv(DATA / f"{name}.csv")
        data[name] = json.loads(df.to_json(orient="records"))      # NaN becomes null
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "/*__DATA__*/" in html, "template has no data placeholder"
    OUT.write_text(html.replace("/*__DATA__*/", payload), encoding="utf-8")
    (OUT.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB) from {len(FILES)} data files")


if __name__ == "__main__":
    main()
