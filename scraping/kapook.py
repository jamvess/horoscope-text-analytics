"""Scrape weekly TAROT horoscopes from horoscope.kapook.com (one article per week, all 12 signs).

How the site works:
- https://horoscope.kapook.com/tarot.php shows the newest articles; its "อ่านต่อ" button calls a JSON API:
  https://cacheportal.kapook.com/api_lite/api_lite_portal.php?portal=horoscope&category=73&page=N&limit=14
  We call that API directly (14 articles per page, newest first).
- Each article has one heading per sign ("ราศีเมษ Aries (13 เม.ย. - 13 พ.ค.)"); the prediction is the text
  between that heading and the next one. Every sign has 6 parts, each starting with a tarot card name.

Usage (run from the project folder):
    python scraping/kapook.py --test     # newest + oldest article in range, prints rows, saves nothing
    python scraping/kapook.py            # -> data/raw/kapook.csv
Default range 2026-05-18 .. 2026-11-09 (26 weeks, same as marumura.csv / sanook.csv).
"""
import argparse
import re
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://cacheportal.kapook.com/api_lite/api_lite_portal.php"
API_PARAMS = {"portal": "horoscope", "category": 73, "limit": 14}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en;q=0.8",
}
DELAY = 1.5     # seconds between requests
MAX_PAGES = 10  # safety limit for the list API

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN_HEADING_RE = re.compile(r"ราศี[ก-๙]+\s*(" + "|".join(SIGNS) + r")\s*\([^)]*\)")
THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5, "มิถุนายน": 6,
    "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
# Title examples (the "12 ราศี" part is missing in older titles):
#   "เช็กเลย ! ดูดวงไพ่ยิปซี 12 ราศี ประจำวันที่ 9 - 15 พฤศจิกายน 2569"
#   "เช็กเลย ! ดูดวงไพ่ยิปซี ประจำวันที่ 1-7 มิถุนายน 2569"
#   "เช็กเลย ! ดูดวงไพ่ยิปซี ประจำวันที่ 29 ธันวาคม 2568 - 4 มกราคม 2569"
TITLE_RE = re.compile(
    r"ดูดวงไพ่ยิปซี (?:12 ราศี )?ประจำวันที่\s*"
    r"(?P<d1>\d{1,2})\s*(?P<m1>[ก-๙]+)?\s*(?:\d{4})?\s*-\s*"
    r"(?P<d2>\d{1,2})\s*(?P<m2>[ก-๙]+)\s*(?P<year>\d{4})"
)


def get(url: str, params: dict | None = None) -> requests.Response | None:
    """Download (up to 3 tries), then wait DELAY seconds."""
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            time.sleep(DELAY)
            return r
        except requests.RequestException as e:
            print(f"   ! error ({type(e).__name__}), retrying..." if attempt < 2 else f"   ! failed: {url}")
            time.sleep(5)
    return None


def week_start(day: int, month: int, published: date) -> date:
    """Pick the year that puts the week start closest to the publish date (safe around New Year)."""
    candidates = [date(published.year + dy, month, day) for dy in (-1, 0, 1)]
    return min(candidates, key=lambda d: abs((d - published).days))


def list_articles(first: date, last: date) -> list[dict]:
    """Call the list API page by page; keep weekly tarot articles whose week is in [first, last]."""
    articles = []
    for page in range(1, MAX_PAGES + 1):
        r = get(API_URL, params={**API_PARAMS, "page": page})
        items = r.json()["data"]["content"] if r else []
        oldest = None
        for item in items:
            m = TITLE_RE.search(item["title"])
            if not m:
                continue  # not a weekly 12-sign article (e.g. "ดวงประจำวันเกิด")
            published = datetime.fromtimestamp(item["ts"]).date()
            month = THAI_MONTHS[m.group("m1") or m.group("m2")]
            week = week_start(int(m.group("d1")), month, published)
            oldest = week
            if first <= week <= last:
                articles.append({"url": item["link"], "week": week, "title": item["title"].strip()})
        print(f"list page {page}: {len(items)} items, oldest weekly article {oldest}")
        if not items or (oldest and oldest < first):
            break
    return articles


def scrape_article(url: str) -> dict[str, str]:
    """Return {english_sign: prediction text} for one weekly article."""
    r = get(url)
    if r is None:
        return {}
    r.encoding = "utf-8"
    content = BeautifulSoup(r.text, "lxml").select_one("div.content")
    if content is None:
        return {}
    # Remove ad/tracking code (e.g. "window._taboola.push(...)" after the last sign)
    for junk in content.find_all(["script", "style", "noscript", "iframe"]):
        junk.decompose()
    full_text = re.sub(r"\s+", " ", content.get_text(" "))

    # Split on the sign headings, e.g. "ราศีเมษ Aries (13 เม.ย. - 13 พ.ค.)".
    # We split the TEXT instead of using <h2> tags because some articles use <h3>/<h4>
    # or put a heading inside another tag.
    headings = list(SIGN_HEADING_RE.finditer(full_text))
    texts = {}
    for k, m in enumerate(headings):
        end = headings[k + 1].start() if k + 1 < len(headings) else len(full_text)
        texts[m.group(1)] = full_text[m.end():end].strip()
    return texts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", default="2026-05-18", help="oldest week (Monday), YYYY-MM-DD")
    parser.add_argument("--last", default="2026-11-09", help="newest week (Monday), YYYY-MM-DD")
    parser.add_argument("--test", action="store_true", help="newest + oldest article only, save nothing")
    args = parser.parse_args()
    first, last = date.fromisoformat(args.first), date.fromisoformat(args.last)

    articles = list_articles(first, last)
    print(f"\n{len(articles)} weekly articles in range\n")
    if args.test:
        articles = [articles[0], articles[-1]]

    rows = []
    for i, art in enumerate(articles, 1):
        texts = scrape_article(art["url"])
        print(f"[{i}/{len(articles)}] {art['week']} {len(texts)} signs  {art['url']}")
        if len(texts) != 12:
            print(f"   ! expected 12 signs, got {len(texts)}: {sorted(texts)}")
        for sign, text in texts.items():
            rows.append({"source": "kapook", "week": art["week"].isoformat(), "zodiac": sign, "text": text})

    df = pd.DataFrame(rows, columns=["source", "week", "zodiac", "text"])
    df = df.drop_duplicates(subset=["week", "zodiac"])
    print(f"\n{len(df)} rows, {df['week'].nunique()} weeks, {df['zodiac'].nunique()} signs")
    expected = pd.date_range(first, last, freq="7D").strftime("%Y-%m-%d")
    print("missing weeks:", sorted(set(expected) - set(df["week"])) or "none")

    if args.test:
        print("\nTest mode: nothing saved. Aries and Pisces of each test article:")
        for _, row in df[df.zodiac.isin(["Aries", "Pisces"])].iterrows():
            print(f"\n--- {row.week} {row.zodiac} ({len(row.text)} chars)\n{row.text}")
        return

    out = PROJECT_ROOT / "data" / "raw" / "kapook.csv"
    if out.exists():  # never overwrite raw data
        out = out.with_name(f"kapook_{datetime.now():%Y%m%d_%H%M}.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
