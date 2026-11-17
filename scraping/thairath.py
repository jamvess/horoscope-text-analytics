"""Scrape weekly zodiac horoscopes from thairath.co.th (writer: หมอไก่ พ.พาทินี).

How the site works:
- /horoscope/weekly_zodiac/<sign>          = this week
- /horoscope/weekly_zodiac/archive         = old weeks; only 4 at first, the "ดูเพิ่ม" button loads
  5 more each click with JavaScript -> we use Selenium to click it and collect the week ids
- /horoscope/weekly_zodiac/archive/<sign>?id=<week id>  = one sign, one week. The page has the data
  as JSON in <script id="__NEXT_DATA__"> (period, writer, content), so plain requests is enough.

Thairath weeks run Sunday-Saturday, so `week` here is a SUNDAY (marumura/sanook use Monday).

Usage (run from the project folder):
    python scraping/thairath.py --test     # Aries, 3 newest weeks, saves nothing
    python scraping/thairath.py            # all 12 signs -> data/raw/thairath.csv
Default range 2026-05-17 .. 2026-11-08 (26 Sunday weeks, same period as marumura.csv/sanook.csv).
"""
import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.thai_text import ZODIAC_TH  # noqa: E402

BASE = "https://www.thairath.co.th/horoscope/weekly_zodiac"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en;q=0.8",
}
DELAY = 1.5      # seconds between requests
MAX_CLICKS = 15  # safety limit for the "ดูเพิ่ม" button (5 weeks per click)
THAI_TZ = timezone(timedelta(hours=7))
ID_RE = re.compile(r"archive/aries\?id=([0-9a-f]{24})")


def get(url: str) -> str:
    """Download a page (up to 3 tries), then wait DELAY seconds."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            time.sleep(DELAY)
            return r.text
        except requests.RequestException as e:
            print(f"   ! error ({type(e).__name__}), retrying..." if attempt < 2 else f"   ! failed: {url}")
            time.sleep(5)
    return ""


def page_data(html: str) -> dict:
    """Return the horoscope part of the JSON inside <script id="__NEXT_DATA__">."""
    script = BeautifulSoup(html, "lxml").find("script", id="__NEXT_DATA__")
    if script is None:
        return {}
    data = json.loads(script.string)
    return data["props"]["initialState"]["horoscope"]["data"].get("items", {})


def id_created(week_id: str) -> date:
    """The id is a MongoDB ObjectId: its first 8 hex digits are the creation time.
    We only use this to know when to stop clicking; the real week comes from the page."""
    return datetime.fromtimestamp(int(week_id[:8], 16), tz=THAI_TZ).date()


def collect_week_ids(first: date, max_clicks: int) -> list[str]:
    """Open the archive with Selenium and click "ดูเพิ่ม" until the ids reach back to `first`."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(f"{BASE}/archive")
        time.sleep(4)  # let the JavaScript load
        ids = list(dict.fromkeys(ID_RE.findall(driver.page_source)))
        print(f"archive: {len(ids)} weeks at start")
        for click in range(1, max_clicks + 1):
            if ids and id_created(ids[-1]) < first - timedelta(days=7):
                break  # old enough
            buttons = [b for b in driver.find_elements(By.TAG_NAME, "button") if "ดูเพิ่ม" in b.text]
            if not buttons:
                print("archive: no more 'ดูเพิ่ม' button")
                break
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();",
                                  buttons[0])
            time.sleep(2.5)
            ids = list(dict.fromkeys(ID_RE.findall(driver.page_source)))
            print(f"archive: click {click} -> {len(ids)} weeks (oldest created {id_created(ids[-1])})")
    finally:
        driver.quit()
    return ids


def scrape_sign_week(slug: str, week_id: str) -> tuple[date | None, str]:
    """Return (week start in Thai time, prediction text) for one sign and one week id."""
    item = page_data(get(f"{BASE}/archive/{slug}?id={week_id}")).get("horoscope") or {}
    if not item.get("content") or not item.get("period"):
        return None, ""
    start_utc = datetime.fromisoformat(item["period"]["start"].replace("Z", "+00:00"))
    week = start_utc.astimezone(THAI_TZ).date()  # e.g. 2026-11-07T17:00Z -> Sunday 2026-11-08
    text = re.sub(r"\s+", " ", item["content"]).strip()
    return week, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", default="2026-05-17", help="oldest week (Sunday), YYYY-MM-DD")
    parser.add_argument("--last", default="2026-11-08", help="newest week (Sunday), YYYY-MM-DD")
    parser.add_argument("--test", action="store_true", help="Aries, 3 newest weeks, save nothing")
    args = parser.parse_args()
    first, last = date.fromisoformat(args.first), date.fromisoformat(args.last)

    # 1) Week ids: this week (from the normal sign page) + old weeks (from the archive)
    current = page_data(get(f"{BASE}/aries")).get("horoscope") or {}
    week_ids = [current["id"]] if current.get("id") else []
    week_ids += collect_week_ids(first, max_clicks=1 if args.test else MAX_CLICKS)
    week_ids = list(dict.fromkeys(week_ids))
    if args.test:
        week_ids = week_ids[:3]
    print(f"\n{len(week_ids)} week ids collected\n")

    # 2) One page per sign per week
    signs = {"เมษ": "Aries"} if args.test else ZODIAC_TH
    rows = []
    for thai_sign, english in signs.items():
        print(f"=== {english} ({thai_sign})")
        for i, week_id in enumerate(week_ids, 1):
            week, text = scrape_sign_week(english.lower(), week_id)
            if week is None:
                print(f"  [{i}/{len(week_ids)}] skip (no data): id={week_id}")
                continue
            if not (first <= week <= last):
                continue  # outside the range (e.g. the current week if it is newer than --last)
            rows.append({"source": "thairath", "week": week.isoformat(), "zodiac": english, "text": text})
            print(f"  [{i}/{len(week_ids)}] {week} {len(text):>4} chars")

    df = pd.DataFrame(rows, columns=["source", "week", "zodiac", "text"])
    df = df.drop_duplicates(subset=["week", "zodiac"])
    print(f"\n{len(df)} rows, {df['week'].nunique()} weeks, {df['zodiac'].nunique()} signs")
    expected = pd.date_range(first, last, freq="7D").strftime("%Y-%m-%d")
    missing = sorted(set(expected) - set(df["week"]))
    print("missing weeks:", missing if missing else "none")

    if args.test:
        print("\nTest mode: nothing saved. Sample rows:")
        print(df.to_string())
        return

    out = PROJECT_ROOT / "data" / "raw" / "thairath.csv"
    if out.exists():  # never overwrite raw data
        out = out.with_name(f"thairath_{datetime.now():%Y%m%d_%H%M}.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
