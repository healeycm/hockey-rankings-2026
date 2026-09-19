# research/roster_talent/harness/scrape.py
"""
Shared polite-fetch helper for CHN pages -- plain HTTP (no Selenium needed;
confirmed by hand that roster/stats pages are static HTML, same as
production's src/data/advanced_metrics_scraper.py already assumes for CHN
box scores). One retry on failure, then skip-and-log -- the same discipline
used throughout research/preseason/'s scrapers.
"""
import time
import urllib.request
import urllib.error

BASE_URL = "https://www.collegehockeynews.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; college hockey roster/draft study; no contact)"}
REQUEST_DELAY_SECONDS = 1.5  # politeness delay between requests


def fetch(path_or_url, retries=1, delay=REQUEST_DELAY_SECONDS):
    """Fetches a CHN page (relative path or full URL). Returns (html, None)
    on success or (None, error_message) on failure -- never raises, so
    callers can skip-and-log without a try/except at every call site."""
    url = path_or_url if path_or_url.startswith("http") else f"{BASE_URL}{path_or_url}"
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            time.sleep(delay)
            return html, None
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code == 404:
                break  # a 404 won't fix itself on retry
        except Exception as e:
            last_error = str(e)
        time.sleep(delay)
    return None, last_error
