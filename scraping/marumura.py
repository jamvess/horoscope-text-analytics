"""Scrape weekly horoscopes from horoscope.marumura.com (WordPress, 1 post per sign per week).

Usage (run from the project folder):
    python scraping/marumura.py --test        # first list page only, prints rows, saves nothing
    python scraping/marumura.py               # last 26 weeks -> data/raw/marumura.csv
    python scraping/marumura.py --weeks 30    # change how many weeks back

Output columns: source, week, zodiac, text  (week = start date of the week, YYYY-MM-DD, Gregorian)
"""
import argparse
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Make "src" importable when this script is run from the project folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.thai_text import ZODIAC_TH  # noqa: E402

LIST_URL = "https://horoscope.marumura.com/ดูดวง/ดูดวงรายสัปดาห์/"
# The site answers "406 Not Acceptable" without browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en;q=0.8",
}
DELAY = 1.5  # seconds between requests (be polite)

THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5, "มิถุนายน": 6,
    "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}

# Title examples:
#   "ดวงรายสัปดาห์ ราศีเมษ 9 – 15 พฤศจิกายน 2569"
#   "ดวงรายสัปดาห์ ราศีมีน 29 ธันวาคม – 4 มกราคม 2568"   (start month written separately)
TITLE_RE = re.compile(
    r"ดวงรายสัปดาห์\s*ราศี(?P<sign>\S+)\s+"
    r"(?P<d1>\d{1,2})\s*(?P<m1>[ก-๙]+)?\s*[–-]\s*"
    r"(?P<d2>\d{1,2})\s*(?P<m2>[ก-๙]+)\s*(?P<year>\d{4})"
)


def get(url: str) -> str:
    """Download a page (up to 3 tries; the site sometimes drops SSL connections), then wait DELAY s."""
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


def sign_to_english(thai_sign: str) -> str | None:
    """'เมษ' -> 'Aries'. Also accepts spellings without the ์ mark (e.g. 'ตุล')."""
    if thai_sign in ZODIAC_TH:
        return ZODIAC_TH[thai_sign]
    for th, en in ZODIAC_TH.items():
        if th.replace("์", "").rstrip("ย") == thai_sign.replace("์", "").rstrip("ย"):
            return en
    return None


def parse_title(title: str):
    """Return (english_sign, day, month) of the week START, or None if the title doesn't match."""
    m = TITLE_RE.search(title)
    if not m:
        return None
    month_name = m.group("m1") or m.group("m2")  # "9 – 15 พฤศจิกายน": start month = end month
    month = THAI_MONTHS.get(month_name)
    sign = sign_to_english(m.group("sign"))
    if month is None or sign is None:
        return None
    return sign, int(m.group("d1")), month


def week_start(day: int, month: int, published: date) -> date:
    """Pick the year that puts the week start closest to the publish date.
    (Titles like '29 ธันวาคม – 4 มกราคม 2568' make the title year unreliable.)"""
    candidates = [date(published.year + dy, month, day) for dy in (-1, 0, 1)]
    return min(candidates, key=lambda d: abs((d - published).days))


def list_posts(n_weeks: int, max_pages: int | None = None) -> list[dict]:
    """Walk the list pages (newest first) and collect post links for the newest n_weeks weeks."""
    posts, weeks_seen, page = [], [], 1
    while True:
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        soup = BeautifulSoup(get(url), "lxml")
        found = 0
        for a in soup.select("article h2 a, article h3 a"):
            title = a.get_text(strip=True)
            if not TITLE_RE.search(title):
                continue
            found += 1
            week_label = TITLE_RE.search(title).group(0).split(" ", 2)[-1]  # e.g. "9 – 15 พฤศจิกายน 2569"
            if week_label not in weeks_seen:
                weeks_seen.append(week_label)
            if len(weeks_seen) > n_weeks:  # reached a week older than we need
                print(f"list page {page}: reached week {n_weeks + 1}, stop")
                return posts
            posts.append({"title": title, "url": a["href"]})
        print(f"list page {page}: {found} posts, {len(weeks_seen)} weeks so far")
        if found == 0 or (max_pages and page >= max_pages):
            return posts
        page += 1


def scrape_post(url: str) -> tuple[str, date | None]:
    """Return (prediction text, publish date) of one post."""
    soup = BeautifulSoup(get(url), "lxml")
    meta = soup.select_one('meta[property="article:published_time"]')
    published = datetime.fromisoformat(meta["content"]).date() if meta else None

    # The prediction is in the content block that starts with "ดวงรายสัปดาห์ ราศี..."
    blocks = [b for b in soup.select(".entry-content div.pk-content-block")
              if "ดวงรายสัปดาห์" in b.get_text()]
    if not blocks:
        return "", published
    parts = []
    for el in blocks[0].find_all(["p", "h4"]):
        if el.name == "h4":  # "เรื่องแนะนำ" (recommended links) = end of the prediction
            break
        text = el.get_text(" ", strip=True)
        if text:
            parts.append(text)
    return " ".join(parts), published


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weeks", type=int, default=26, help="how many weeks back")
    parser.add_argument("--test", action="store_true", help="first list page only, save nothing")
    args = parser.parse_args()

    posts = list_posts(args.weeks, max_pages=1 if args.test else None)
    print(f"\n{len(posts)} posts to download\n")

    rows = []
    for i, post in enumerate(posts, 1):
        parsed = parse_title(post["title"])
        if parsed is None:
            print(f"[{i}/{len(posts)}] skip (cannot read title): {post['title']}")
            continue
        sign, day, month = parsed
        text, published = scrape_post(post["url"])
        if not text or published is None:
            print(f"[{i}/{len(posts)}] skip (no text/date): {post['url']}")
            continue
        week = week_start(day, month, published)
        rows.append({"source": "marumura", "week": week.isoformat(), "zodiac": sign, "text": text})
        print(f"[{i}/{len(posts)}] {week} {sign:<12} {len(text):>4} chars")

    df = pd.DataFrame(rows, columns=["source", "week", "zodiac", "text"])
    df = df.drop_duplicates(subset=["week", "zodiac"])
    print(f"\n{len(df)} rows, {df['week'].nunique()} weeks, {df['zodiac'].nunique()} signs")
    print(df.groupby("week").size().to_string())

    if args.test:
        print("\nTest mode: nothing saved. Sample rows:")
        print(df.head(3).to_string())
        return

    out = PROJECT_ROOT / "data" / "raw" / "marumura.csv"
    if out.exists():  # never overwrite raw data: write a new file name instead
        out = out.with_name(f"marumura_{datetime.now():%Y%m%d_%H%M}.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
