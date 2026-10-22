"""Week 1 probe: check which data sources respond from this machine.

Prints HTTP status, content type and size for each candidate URL so the
data inventory can record what is actually downloadable. Downloads nothing.
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (research project; india-economic-pulse)"}

CANDIDATES = {
    "NPCI UPI stats page": "https://www.npci.org.in/what-we-do/upi/product-statistics",
    "NPCI UPI stats (alt)": "https://www.npci.org.in/product/upi/product-statistics",
    "PPAC home": "https://ppac.gov.in/",
    "PPAC consumption page": "https://ppac.gov.in/consumption/products-wise",
    "data.gov.in": "https://data.gov.in/",
    "GST portal downloads": "https://tutorial.gst.gov.in/downloads/",
    "GST portal stats": "https://www.gst.gov.in/download/gststatistics",
    "GST council collections (PIB)": "https://www.pib.gov.in/",
    "MoSPI home": "https://mospi.gov.in/",
    "MoSPI eSankhyiki": "https://esankhyiki.mospi.gov.in/",
    "MoSPI release calendar": "https://mospi.gov.in/release-calendar",
    "RBI payment systems": "https://www.rbi.org.in/",
}


def probe(name: str, url: str) -> None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        print(f"{name:<32} {r.status_code}  {r.headers.get('content-type', '?')[:40]:<40} "
              f"{len(r.content):>9,} bytes  -> {r.url[:70]}")
    except Exception as e:  # network/SSL/timeouts are the interesting failures here
        print(f"{name:<32} FAIL  {type(e).__name__}: {str(e)[:80]}")


if __name__ == "__main__":
    for n, u in CANDIDATES.items():
        probe(n, u)
