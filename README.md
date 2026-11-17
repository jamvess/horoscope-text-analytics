# ดวงใครก็ดวงมัน? Text Analytics ของดวงรายสัปดาห์ 12 ราศี

**Is Your Horoscope Really Yours? A Text Analytics Study of Thai Weekly Horoscopes**
CPE393 Special Topic III: Text Analytics, Text Mining and Social Network Analysis (มจธ.)

คำถาม: คำทำนายดวงรายสัปดาห์ของ 12 ราศีต่างกันจริง หรือเขียนกว้างจนใช้ได้กับทุกคน (Barnum effect)
ข้อมูล: 1,233 คำทำนายจาก 4 เว็บ (marumura, sanook, thairath, kapook) ในช่วง 26 สัปดาห์

**ผลสรุป:** คำทำนายต่างกันตาม**คนเขียน (เว็บ)** ไม่ใช่ตาม**ราศี**
- ทายเว็บได้ 100% แต่ทายราศีได้แค่ระดับเดาสุ่ม
- ได้ข้อสรุปเดียวกันจาก 7 วิธี: classification, similarity, LDA, BERTopic, clustering, sentiment, summarization

รายละเอียดทุกขั้นตอน (ทำอะไร, โค้ด, เหตุผล, ปัญหาที่เจอ): **[docs/project_log.md](docs/project_log.md)**
กติกาการทำงานของทีม: **[CLAUDE.md](CLAUDE.md)**

## เริ่มใช้งานบนเครื่องตัวเอง (Windows)

```bash
git clone https://github.com/jamvess/horoscope-text-analytics.git
cd horoscope-text-analytics
python -m venv .venv                      # Python 3.12 หรือ 3.13
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe check_setup.py   # ต้องขึ้น SETUP OK
```

ถ้าจะรัน 04 (BERTopic) หรือ 05 (sentiment) ต้องติดตั้ง ML packages เพิ่ม (ประมาณ 2 GB) ตามขั้นตอนใน [requirements-ml.txt](requirements-ml.txt)

ข้อมูลที่ดึงมาแล้ว (`data/raw/`) และไฟล์ cache (`outputs/*.csv`, `outputs/*.npy`) อยู่ใน repo แล้ว **จึงไม่ต้อง scrape ใหม่** และ notebook ที่ใช้เวลานาน (04, 05) จะโหลดจาก cache

## โครงสร้างโฟลเดอร์

| โฟลเดอร์ | มีอะไร |
|---|---|
| `scraping/` | สคริปต์ดึงข้อมูล 4 เว็บ |
| `src/` | `thai_text.py` (ตัดคำ/ลบชื่อราศี ใช้ร่วมกันทุก notebook) และ `build_dataset.py` (รวมและทำความสะอาดข้อมูล) |
| `data/raw/`, `data/processed/` | ข้อมูลดิบ และ `horoscopes.csv` ที่ทำความสะอาดแล้ว |
| `notebooks/` | `01_eda` ถึง `07_summarization` |
| `outputs/figures/` | กราฟทั้งหมดที่ใช้ในรายงาน (รูปที่ 1–19) |
| `docs/` | proposal, slides (`presentation_TH.pptx`), project log, เอกสารประกอบวิชา |

## ทำงานร่วมกันผ่าน GitHub

1. **ก่อนเริ่มงานทุกครั้ง:** `git pull`
2. **แก้เฉพาะไฟล์ที่ตัวเองรับผิดชอบ** (ดูตาราง owner ใน CLAUDE.md) เพราะไฟล์ `.ipynb`, `.pptx` และ `.docx` merge กันยาก ถ้าสองคนแก้ไฟล์เดียวกันพร้อมกันจะเกิด conflict
3. **เสร็จแล้ว:** `git add <ไฟล์ที่แก้>` → `git commit -m "อธิบายสั้นๆ ว่าแก้อะไร"` → `git push`
4. ถ้าจะแก้ `src/thai_text.py` หรือไฟล์ใน `data/` ให้บอกในกลุ่มก่อน เพราะทุกคนใช้ร่วมกัน
