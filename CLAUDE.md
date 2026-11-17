# Horoscope Text Analytics (CPE393 mini project)

Course: CPE393 Special Topic III: Text Analytics, Text Mining and Social Network Analysis (KMUTT).
Instructor: Dr. Sansiri Tarnpradab. Team of 6 students. Shared on GitHub (public): https://github.com/jamvess/horoscope-text-analytics
— `git pull` before starting, commit only your own files, `git push` when done (see README.md).
Talk to the team in Thai. Write code, comments and file names in English.

## Research question
Do Thai weekly horoscopes for the 12 zodiac signs actually differ, or are they written so broadly
that they fit anyone (Barnum effect)?

Objectives:
1. Measure how similar the predictions are across the 12 signs, and test whether a model can identify
   the sign from the prediction text.
2. Find the main topics horoscopes talk about (work, money, love, health, luck).
3. Compare sentiment (positive / neutral / negative) across signs and across websites.

Key comparison: predict the SIGN (12 classes, chance 8.3%) vs predict the WEBSITE (4 classes, chance 25%).
- Sign near chance + website high -> differences come from the writer, not the sign (Barnum effect).
- Sign well above chance -> signs really differ; use topic modeling to explain how.
Do not assume either outcome. Report what the data shows.

## Data sources (weekly horoscopes, 12 signs, about 6 months back)
| source     | URL | notes |
|------------|-----|-------|
| marumura   | https://horoscope.marumura.com/ดูดวง/ดูดวงรายสัปดาห์/ | WordPress list, 1 post per sign per week, pagination /page/N/. Easiest; start here. |
| sanook     | https://www.sanook.com/horoscope/myhoro/7days/ | one page per sign; check how far back old weeks go |
| thairath   | https://www.thairath.co.th/horoscope/weekly_zodiac | blocks simple bots; may need Selenium |
| kapook     | https://horoscope.kapook.com/tarot.php | one article per week with all 12 signs (tarot-based, not astrology) |
Backup if a site fails: Sanook weekly horoscope articles at https://www.sanook.com/horoscope/ (search "ดวง 12 ราศี สัปดาห์นี้").
Target: about 1,250 rows in total (12 signs x 26 weeks x 4 sites).

## Data schema (every CSV, UTF-8)
source, week, zodiac, text
- week: start date of the horoscope week, YYYY-MM-DD, Gregorian (convert Buddhist year: 2569 -> 2026)
- zodiac: English name (Aries, Taurus, Gemini, Cancer, Leo, Virgo, Libra, Scorpio, Sagittarius, Capricorn, Aquarius, Pisces)
- text: the full prediction for that sign (if a site splits work/money/love sections, join them into one text)
- Raw: data/raw/<source>.csv. Combined and cleaned: data/processed/horoscopes.csv

## Analysis plan (one notebook each, in notebooks/)
| notebook | owner | method | evaluation / output |
|----------|-------|--------|---------------------|
| 01_eda | Member 2 | text length per site/sign, top words, word cloud per sign | histograms, boxplots, 12 word clouds |
| 02_similarity | Member 3 | TF-IDF per sign (all texts of a sign joined) + cosine similarity | 12x12 heatmap, mean within-sign vs between-sign similarity |
| 03_classification | Member 4 | TF-IDF + Naive Bayes / Logistic Regression / SVM, 80:20 stratified split | accuracy, precision, recall, F1, confusion matrix, vs chance level |
| 04_topic | Member 5 | LSA vs LDA (gensim) vs BERTopic (L10), choose k by coherence score | top words per topic, topic share per site and per sign |
| 05_sentiment | Member 6 | pre-trained Thai sentiment model (e.g. WangchanBERTa-based), no training | share positive per sign and per site, ranking charts |
Member 1 owns scraping/. Save every chart for the report to outputs/figures/ (PNG, Thai font).

## Stretch goals: ONLY after notebooks 01-05 are finished and their charts are saved
They extend the same story (sign vs writer) with lectures L8-L10. Do them in this order; stop when time runs out.
| notebook | owner | lecture | idea | output |
|----------|-------|---------|------|--------|
| 06_clustering | Member 3 | L9 | K-means on TF-IDF of all texts, no labels. Choose k by elbow (WCSS) + silhouette, and also try k=12 and k=4. Question: do the clusters group by SIGN or by WEBSITE? Cross-tab clusters vs sign and vs source; Adjusted Rand Index for each. | elbow plot, 2 PCA scatter plots side by side (colored by sign / by site), cross-tab heatmaps, ARI table |
| 04_topic (extra cells) | Member 5 | L10 | Topics over time (BERTopic topics_over_time, or LDA topic share per week): does money/luck talk rise around payday (end of month) or near lottery draw days (1st and 16th)? Topic x sign heatmap. | line chart of topic share by week, topic-by-sign heatmap |
| 07_summarization | Member 1 | L8 | Extractive summary (TextRank/LexRank, Lead-3 as baseline) of 6 months for each sign: "ดวงครึ่งปีของแต่ละราศีใน 3 ประโยค". Then ROUGE between the 12 sign summaries as a second similarity measure (high ROUGE = interchangeable horoscopes). Also one "universal horoscope" summarizing ALL texts. | table of 12 summaries, ROUGE heatmap, the universal horoscope text |
Optional if still more time: chi-square test on lucky numbers; Word2Vec nearest words to "โชค", "เงิน", "ความรัก" (L6).

Presentation hook (no extra analysis): show the audience 3 real horoscopes with sign names removed and the
"universal horoscope"; let them guess the sign, then show that the model guesses about as well as they do.

## Course scope (stay close to what was taught)
L2 regex, L3 visualization (word cloud, bar chart, heatmap, LDA topics), L4 web scraping (Requests,
BeautifulSoup, Selenium), L5 data preparation (PyThaiNLP), L6 features (one-hot, BoW, TF-IDF, Word2Vec),
L7 classification (Naive Bayes, SVM, kNN, decision tree, LSTM; precision/recall/F1),
L8 summarization (extractive: Lead-3, TextRank, LexRank; abstractive; ROUGE),
L9 clustering (cosine/Euclidean distance, K-means, elbow/WCSS, cluster quality),
L10 topic modeling (LSA, LDA, BERTopic with c-TF-IDF, topics over time).
Prefer these methods. Pre-trained sentiment models are an allowed extra.

## Timeline (4 weeks)
1. Scrape all 4 sites -> data/raw (Member 1, Member 2 helps with Selenium)
2. Combine, clean, EDA (Member 2); others prepare their notebooks
3. Similarity / classification / topics / sentiment (Members 3-6); free members start stretch goals
4. Stretch goals if time, then report and slides (Member 6 with everyone)
Check the real presentation date with the instructor (L10 slides show a presentation date) and squeeze the plan if it is sooner.

Final report follows the course examples: cover, Introduction (background, objectives, dataset),
Method, Results (every figure explained: "จากกราฟ พบว่า..."), Discussion (incl. limitations), Conclusion, References.

## Folders
- scraping/          one script per site: marumura.py, sanook.py, thairath.py, kapook.py
- src/thai_text.py   shared Thai preprocessing: clean_text(), tokenize(), THAI_FONT, ZODIAC_TH
- notebooks/         01_eda ... 05_sentiment, then stretch: 06_clustering, 07_summarization
- data/raw, data/processed, outputs/figures
- fonts/Sarabun-Regular.ttf  Thai font for word clouds and matplotlib
- docs/              proposal_EN.docx / proposal_TH.docx, lectures/ (slides L01-L10), example_reports/ (past student reports: follow their structure for our report)

## Rules
- Environment: Windows + Git Bash, Python 3.12 in .venv. Install packages with `python -m pip install ...`
  (this .venv was created by uv, so plain `pip` may install to the wrong Python). Add new packages to requirements.txt.
- Heavy packages (torch, transformers, bertopic) are in requirements-ml.txt; install only when week 3 starts.
  Summarization/ROUGE packages are not installed yet; add them to requirements-ml.txt when 07 starts.
- Scraping: check robots.txt, wait 1-2 s between requests, test on 1-2 pages before a full run, print progress.
- Never overwrite data/raw files without asking; write a new file name instead.
- Use src/thai_text.py for preprocessing in every notebook. Ask the team before changing it (everyone depends on it).
- Remove zodiac sign names from text before similarity/classification (clean_text does this by default).
- Thai text in charts must use fonts/Sarabun-Regular.ttf (WordCloud font_path; matplotlib font manager).
- Shared repo: before editing a file another member owns (see owner column), ask first. .ipynb/.pptx/.docx do not merge,
  so only one person edits each of them at a time. The repo is public: never commit passwords, tokens or personal data.
- Keep code simple and commented; we are students learning. Explain results in plain Thai after each step.
- Work one step at a time: propose a short plan, do it, show the result, then wait.