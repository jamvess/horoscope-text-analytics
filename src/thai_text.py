"""Shared Thai text preprocessing for the horoscope project.

Usage:
    from src.thai_text import clean_text, tokenize, THAI_FONT
    tokens = tokenize(clean_text(text))
"""
import re
from pathlib import Path

from pythainlp.corpus import thai_stopwords, thai_words
from pythainlp.tokenize import Tokenizer
from pythainlp.util import normalize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THAI_FONT = str(PROJECT_ROOT / "fonts" / "Sarabun-Regular.ttf")

# Thai name -> English name (also used to remove sign names from the text)
ZODIAC_TH = {
    "เมษ": "Aries", "พฤษภ": "Taurus", "เมถุน": "Gemini", "กรกฎ": "Cancer",
    "สิงห์": "Leo", "กันย์": "Virgo", "ตุลย์": "Libra", "พิจิก": "Scorpio",
    "ธนู": "Sagittarius", "มังกร": "Capricorn", "กุมภ์": "Aquarius", "มีน": "Pisces",
}
# Spellings that also appear on some sites
# (มิถุน = Gemini, มกร = Capricorn, สันย์ = sanook typo for กันย์; added 2026-11-14, see docs/project_log.md)
EXTRA_SIGN_SPELLINGS = ["ตุล", "กันย", "กุมภ", "ตุลย", "มิถุน", "มกร", "สันย์"]

# Astrology words the default dictionary may split wrongly. Add more as you find them.
ASTRO_WORDS = [
    "ผู้ใหญ่อุปถัมภ์", "ดาวพฤหัส", "ดาวเสาร์", "ดาวราหู", "ดาวศุกร์", "ดาวอังคาร",
    "ดาวพุธ", "ดาวเกตุ", "โชคลาภ", "เนื้อคู่", "สีมงคล", "เลขมงคล", "ทำบุญ",
] + [f"ราศี{name}" for name in ZODIAC_TH]

_tokenizer = Tokenizer(custom_dict=set(thai_words()) | set(ASTRO_WORDS), engine="newmm")
STOPWORDS = set(thai_stopwords()) | {"ราศี", "ชาว", "สัปดาห์", "นี้", "ช่วง"}

_sign_names = sorted(list(ZODIAC_TH) + EXTRA_SIGN_SPELLINGS, key=len, reverse=True)
_SIGN_SET = set(_sign_names)
# "ราศี" + sign name: safe to remove with regex because of the "ราศี" prefix
_prefixed_sign_pattern = re.compile("ราศี?(" + "|".join(_sign_names) + ")")


def clean_text(text: str, remove_signs: bool = True) -> str:
    """Normalize Thai text, drop URLs/symbols, and (by default) remove zodiac sign names."""
    text = normalize(str(text))
    text = re.sub(r"https?://\S+", " ", text)
    if remove_signs:
        text = _prefixed_sign_pattern.sub(" ", text)  # "ชาวราศีเมษ" -> "ชาว "
        # A sign name WITHOUT "ราศี" is removed only if the tokenizer sees it as a whole word
        # ("ชาวเมษ" -> "ชาว"). A plain regex would also cut words that contain a sign name:
        # "มีนัด" (มีน), "ตุลาคม" (ตุล), "พากันยกธง" (กันย). Fixed 2026-11-14, see docs/project_log.md.
        text = "".join(" " if tok in _SIGN_SET else tok for tok in _tokenizer.word_tokenize(text))
    text = re.sub(r"[^฀-๿a-zA-Z0-9\s]", " ", text)  # keep Thai, English, digits
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Split Thai text into words with PyThaiNLP (newmm + astrology words)."""
    tokens = [t.strip() for t in _tokenizer.word_tokenize(text)]
    tokens = [t for t in tokens if t and not t.isdigit() and len(t) > 1]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens
