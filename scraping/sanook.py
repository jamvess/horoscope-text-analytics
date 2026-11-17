"""Scrape weekly horoscopes from sanook.com (one article per sign per week).

Old weeks are found through the tag page of each sign, e.g.
    https://www.sanook.com/horoscope/tag/ดูดวงรายสัปดาห์ ราศีเมษ/          (newest 20 weeks)
    https://www.sanook.com/horoscope/tag/ดูดวงรายสัปดาห์ ราศีเมษ/page/2/   (20 weeks older)

Usage (run from the project folder):
    python scraping/sanook.py --test      # Aries only, prints rows, saves nothing
    python scraping/sanook.py             # all 12 signs -> data/raw/sanook.csv
The default week range matches marumura.csv (2026-05-18 .. 2026-11-09, 26 weeks).

Output columns: source, week, zodiac, text  (week = Monday the article was published, YYYY-MM-DD)
"""
import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.thai_text import ZODIAC_TH  # noqa: E402

TAG_URL = "https://www.sanook.com/horoscope/tag/ดูดวงรายสัปดาห์ ราศี{sign}/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en;q=0.8",
}
DELAY = 1.5  # seconds between requests
MAX_TAG_PAGES = 5  # safety limit (20 articles per tag page)

# Weekly articles that sanook forgot to tag, so they are missing from the tag pages.
# Found by hand (IDs of one week go up by 4 in sign order: Aries, Taurus, ... Pisces).
# Gemini 2026-06-15 has a broken link on the tag page and its article gives 404: it does not exist.
EXTRA_ARTICLES = {
    "มังกร": ["https://www.sanook.com/horoscope/328466/"],  # Capricorn, week 2026-06-15
    "สิงห์": ["https://www.sanook.com/horoscope/333858/"],  # Leo, week 2026-09-21
}


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


def monday_of(d: date) -> date:
    """Week start = Monday of the week that contains d."""
    return d - timedelta(days=d.weekday())


def list_articles(thai_sign: str, first: date, last: date) -> list[dict]:
    """Walk the tag pages of one sign (newest first); keep articles whose week is in [first, last]."""
    articles = []
    for page in range(1, MAX_TAG_PAGES + 1):
        url = TAG_URL.format(sign=thai_sign) + (f"page/{page}/" if page > 1 else "")
        soup = BeautifulSoup(get(url), "lxml")
        cards = soup.select("article.PostListWithDetail")  # the tag's own list (sidebar items excluded)
        oldest = None
        for card in cards:
            link, tm = card.find("a", href=True), card.find("time")
            title = link.get("title", "") if link else ""
            if not tm or not title.startswith("ดูดวงรายสัปดาห์ ราศี"):
                continue
            week = monday_of(datetime.strptime(tm["datetime"][:10], "%Y-%m-%d").date())
            oldest = week
            if not link["href"].startswith("http"):  # broken link on the site (seen once)
                print(f"  ! broken link for week {week}: {link['href']!r}, skipped")
                continue
            if first <= week <= last:
                articles.append({"url": link["href"], "week": week})
        print(f"  tag page {page}: {len(cards)} cards, oldest week {oldest}")
        if not cards or (oldest and oldest < first):  # gone past the range -> stop
            break
    return articles


def scrape_article(url: str) -> tuple[str, date | None]:
    """Return (prediction text, publish date) of one article."""
    soup = BeautifulSoup(get(url), "lxml")
    meta = soup.select_one('meta[name="published_date"]')
    published = datetime.fromisoformat(meta["content"]).date() if meta else None
    body = soup.select_one("#EntryReader_0")
    if body is None:
        return "", published
    # Each section (intro, การเงิน, การงาน, ความรัก, สุขภาพ, คำแนะนำ) is a <p>; join them
    parts = [p.get_text(" ", strip=True) for p in body.find_all("p")]
    return " ".join(t for t in parts if t), published


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", default="2026-05-18", help="oldest week (Monday), YYYY-MM-DD")
    parser.add_argument("--last", default="2026-11-09", help="newest week (Monday), YYYY-MM-DD")
    parser.add_argument("--test", action="store_true", help="Aries only, save nothing")
    args = parser.parse_args()
    first, last = date.fromisoformat(args.first), date.fromisoformat(args.last)

    signs = ["เมษ"] if args.test else list(ZODIAC_TH)
    rows = []
    for thai_sign in signs:
        english = ZODIAC_TH[thai_sign]
        print(f"\n=== {english} ({thai_sign})")
        articles = list_articles(thai_sign, first, last)
        # week=None: the real week comes from the article's own published_date
        articles += [{"url": u, "week": None} for u in EXTRA_ARTICLES.get(thai_sign, [])]
        for i, art in enumerate(articles, 1):
            text, published = scrape_article(art["url"])
            # Prefer the date inside the article; fall back to the tag page date
            week = monday_of(published) if published else art["week"]
            if not text or week is None or not (first <= week <= last):
                print(f"  [{i}/{len(articles)}] skip (no text or week out of range): {art['url']}")
                continue
            rows.append({"source": "sanook", "week": week.isoformat(), "zodiac": english, "text": text})
            print(f"  [{i}/{len(articles)}] {week} {len(text):>5} chars  {art['url']}")

    df = pd.DataFrame(rows, columns=["source", "week", "zodiac", "text"])
    n_before = len(df)
    df = df.drop_duplicates(subset=["week", "zodiac"])
    print(f"\n{len(df)} rows ({n_before - len(df)} duplicate week+sign removed), "
          f"{df['week'].nunique()} weeks, {df['zodiac'].nunique()} signs")
    print(df.groupby("zodiac").size().to_string())

    if args.test:
        print("\nTest mode: nothing saved. Newest and oldest text:")
        for idx in (0, len(df) - 1):
            print(f"\n--- {df.week.iloc[idx]}\n{df.text.iloc[idx]}")
        return

    out = PROJECT_ROOT / "data" / "raw" / "sanook.csv"
    if out.exists():  # never overwrite raw data
        out = out.with_name(f"sanook_{datetime.now():%Y%m%d_%H%M}.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
