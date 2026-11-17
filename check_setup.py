"""Run this once after installing: python check_setup.py
It checks the packages, Thai word tokenization, and that word clouds can show Thai."""
import importlib
import sys
from pathlib import Path

ok = True
print(f"Python {sys.version.split()[0]}")
if sys.version_info < (3, 10):
    print("  !! Python 3.10 or newer is needed (3.11 or 3.12 recommended)")
    ok = False

for pkg in ["requests", "bs4", "lxml", "selenium", "pandas", "numpy", "matplotlib",
            "seaborn", "wordcloud", "pythainlp", "sklearn", "gensim"]:
    try:
        importlib.import_module(pkg)
        print(f"  ok  {pkg}")
    except ImportError:
        print(f"  !!  {pkg} is missing -> pip install -r requirements.txt")
        ok = False

if ok:
    from src.thai_text import THAI_FONT, clean_text, tokenize
    sample = "ชาวราศีสิงห์ สัปดาห์นี้มีโชคก้อนใหญ่ ผู้ใหญ่อุปถัมภ์ การงานก้าวหน้า"
    print("\nTokenize test:", tokenize(clean_text(sample)))

    from wordcloud import WordCloud
    out = Path("outputs/figures/_setup_test_wordcloud.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    WordCloud(font_path=THAI_FONT, background_color="white", width=500, height=300,
              regexp=r"[^\s]+").generate(" ".join(tokenize(clean_text(sample)) * 3)).to_file(out)
    print(f"Word cloud saved to {out} -> open it: Thai words should be readable, not boxes")

print("\nSETUP OK" if ok else "\nSETUP NOT COMPLETE (see !! above)")
