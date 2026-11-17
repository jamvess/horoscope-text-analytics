"""Combine the 4 raw CSV files into data/processed/horoscopes.csv (step 5: combine + clean).

Run from the project folder:
    python src/build_dataset.py

What it does (decisions agreed by the team, see docs/project_log.md "ขั้นที่ 5"):
1. Read data/raw/{marumura,sanook,thairath,kapook}.csv and stack them.
2. week_monday: thairath weeks start on Sunday, the other 3 sites on Monday -> shift thairath by +1 day
   so the same week has the same key on every site. The original `week` column is kept.
3. Three versions of the text:
   - text_raw    : exactly as scraped
   - text        : MAIN text for all notebooks. Removes text that tells the sign without being a prediction:
                   * sanook: the intro paragraph that is identical every week ("สวัสดีค่ะ ชาวราศีเมษ ราศีแห่งนักรบผู้กล้า...")
                   * kapook: tarot card names ("Six of Pentacles", "The Magician (กลับหัว)") = random draws
   - text_strict : like `text`, and also removes sanook's "คำแนะนำ" section (planet transit text that names
                   the sign's ruling planet and is reused for several weeks). Use it to check if results change.
4. near_duplicate: TF-IDF (character 3-5 grams) + cosine similarity on `text`. If a row is > 0.7 similar to an
   OLDER row, it is flagged and `dup_of` says which row it copies. The oldest copy is never flagged, so
   df[~df.near_duplicate] keeps one copy of every text.
Sign names are NOT removed here: notebooks still call clean_text() from src/thai_text.py for that.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw"
OUT = PROJECT_ROOT / "data" / "processed" / "horoscopes.csv"
SOURCES = ["marumura", "sanook", "thairath", "kapook"]
SIGN_ORDER = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
              "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
DUP_THRESHOLD = 0.7

# --- kapook: tarot card names (78-card deck, plus spellings seen on the site like "Ace of Sword") ---
_RANKS = "Ace|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Page|Knight|Queen|King"
_SUITS = "Cups|Pentacles|Swords?|Wands?"
_MAJOR = ("Wheel of Fortune|The Hanged Man|The High Priestess|The [A-Z][a-z]+"
          "|Death|Judgement|Justice|Strength|Temperance")
# (?<![A-Za-z]) / (?![A-Za-z]) instead of \b: Thai letters count as "word" characters, so \b fails when a
# card name is glued to Thai text with no space, e.g. "The Hermitรายได้ไม่ค่อยดี"
CARD_RE = re.compile(rf"(?<![A-Za-z])(?:(?:The )?(?:{_RANKS}) of (?:{_SUITS})|{_MAJOR})(?![A-Za-z])"
                     r"(?:\s*\(กลับหัว\))?")

# --- sanook: the "คำแนะนำ" section header is the word on its own, after the "สุขภาพ" section ---
# (inside the text the word also appears joined to others, e.g. "ทำตามคำแนะนำอย่างมีเหตุผล")
ADVICE_RE = re.compile(r"(?<=\s)คำแนะนำ(?=\s)")


def squeeze(text: str) -> str:
    """Collapse repeated spaces."""
    return re.sub(r"\s+", " ", text).strip()


def sanook_main(text: str) -> str:
    """Drop the weekly-identical intro: keep everything from the first section header 'การเงิน'."""
    start = text.find("การเงิน")
    return text[start:] if start >= 0 else text


def sanook_strict(text: str) -> str:
    """sanook_main + drop the 'คำแนะนำ' section (first stand-alone header after 'สุขภาพ')."""
    text = sanook_main(text)
    health = max(text.find(" สุขภาพ "), 0)
    m = ADVICE_RE.search(text, health)
    return text[:m.start()] if m else text


def kapook_main(text: str) -> str:
    """Remove tarot card names; the Thai section headers and meanings stay."""
    return CARD_RE.sub(" ", text)


def flag_near_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows that copy an older row (cosine > DUP_THRESHOLD on character n-gram TF-IDF)."""
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(df["text"])
    S = cosine_similarity(X)
    np.fill_diagonal(S, 0)
    labels = (df["source"] + " " + df["week"] + " " + df["zodiac"]).to_numpy()
    weeks = df["week_monday"].to_numpy()

    flags, dup_of, dup_sim = [], [], []
    for j in range(len(df)):
        # candidates = rows that are older than j (earlier week, or same week but earlier in the table)
        older = (weeks < weeks[j]) | ((weeks == weeks[j]) & (np.arange(len(df)) < j))
        sims = np.where(older, S[j], 0)
        best = int(sims.argmax())
        is_dup = sims[best] > DUP_THRESHOLD
        flags.append(bool(is_dup))
        dup_of.append(labels[best] if is_dup else "")
        dup_sim.append(round(float(sims[best]), 3) if is_dup else np.nan)
    return df.assign(near_duplicate=flags, dup_of=dup_of, dup_sim=dup_sim)


def main():
    # 1) Read and stack
    df = pd.concat([pd.read_csv(RAW / f"{s}.csv") for s in SOURCES], ignore_index=True)
    print(f"read {len(df)} rows from {len(SOURCES)} files")

    # 2) Same week key on every site
    week = pd.to_datetime(df["week"])
    df["week_monday"] = (week + pd.to_timedelta((df["source"] == "thairath").astype(int), unit="D")
                         ).dt.strftime("%Y-%m-%d")
    assert (pd.to_datetime(df["week_monday"]).dt.day_of_week == 0).all(), "week_monday must be a Monday"

    # 3) Text versions
    df["text_raw"] = df["text"]
    main_text, strict_text = [], []
    for source, raw in zip(df["source"], df["text_raw"]):
        if source == "sanook":
            main_text.append(sanook_main(raw))
            strict_text.append(sanook_strict(raw))
        elif source == "kapook":
            main_text.append(kapook_main(raw))
            strict_text.append(kapook_main(raw))
        else:
            main_text.append(raw)
            strict_text.append(raw)
    df["text"] = [squeeze(t) for t in main_text]
    df["text_strict"] = [squeeze(t) for t in strict_text]

    # Sort: site, week, sign (the near-duplicate check uses this order for "older")
    df["zodiac"] = pd.Categorical(df["zodiac"], categories=SIGN_ORDER, ordered=True)
    df = df.sort_values(["source", "week_monday", "zodiac"]).reset_index(drop=True)
    df["zodiac"] = df["zodiac"].astype(str)

    # 4) Near-duplicates
    df = flag_near_duplicates(df)

    cols = ["source", "week", "week_monday", "zodiac", "text", "text_strict", "text_raw",
            "near_duplicate", "dup_of", "dup_sim"]
    df = df[cols]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")

    # 5) Summary
    summary = df.assign(
        len_raw=df["text_raw"].str.len(), len_text=df["text"].str.len(), len_strict=df["text_strict"].str.len(),
        cross_sign_dup=df["near_duplicate"] & (df["dup_of"].str.split().str[-1] != df["zodiac"]),
    ).groupby("source").agg(
        rows=("text", "size"), weeks=("week_monday", "nunique"),
        mean_len_raw=("len_raw", "mean"), mean_len_text=("len_text", "mean"),
        mean_len_strict=("len_strict", "mean"),
        near_dup=("near_duplicate", "sum"), cross_sign_dup=("cross_sign_dup", "sum"),
    ).round(0)
    print(summary.to_string())
    print(f"\ntotal {len(df)} rows, {df['near_duplicate'].sum()} flagged near_duplicate")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
