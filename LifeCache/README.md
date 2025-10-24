# LifeCache – AI-Powered Time Capsule

LifeCache lets families upload text and audio memories, analyzes them for emotion and themes, and generates a Memory Book PDF. It also supports scheduling deliveries (MVP: log-based) for future dates.

## Quickstart

### 1) Create virtualenv and install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 2) Run the Streamlit app

```bash
streamlit run streamlit_app/main.py
```

App will create an SQLite DB at `data/lifecache.db` and folders under `data/`.

### 3) Optional: Run the FastAPI service (not required for UI)

```bash
uvicorn backend.app:app --reload
```

### 4) Optional: Start the scheduler (background log delivery)

```bash
python -c "from backend.scheduler import start_scheduler; start_scheduler(); import time; time.sleep(120)"
```

This will log deliveries to `data/deliveries/deliveries.log` once delivery times are due.

## Features in this MVP
- Upload text or audio (audio transcription if `speech_recognition` + PocketSphinx available)
- NLP analysis: VADER-based emotion scoring + keyword heuristics
- Summarization via LexRank (`sumy`)
- PDF Memory Book with excerpts and emotion chart (FPDF + Matplotlib)
- Scheduler for due deliveries (log channel)

## Notes
- For offline STT, install PocketSphinx packages; otherwise set `ALLOW_ONLINE_STT=1` to enable Google Web Speech fallback.
- This is a local, privacy-first prototype. Replace the log channel with an email provider for real delivery.
