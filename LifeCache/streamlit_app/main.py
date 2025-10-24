from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import streamlit as st

import sys
from pathlib import Path as _Path
sys.path.append(str(_Path(__file__).resolve().parents[1]))

from backend import database
from backend.utils.pdf_generator import generate_memory_book
from nlp.emotion import analyze_text_emotions
from nlp.summarizer import summarize_text
from nlp.stt import transcribe_audio

st.set_page_config(page_title="LifeCache", page_icon="🧠", layout="wide")


def ensure_db() -> None:
    database.initialize_database()


def sidebar_capsules() -> Optional[int]:
    st.sidebar.header("Capsules")
    rows = database.list_capsules()
    capsule_options = {f"#{r['id']} – {r['title']}": int(r["id"]) for r in rows}
    choice = st.sidebar.selectbox("Select capsule", options=["(none)"] + list(capsule_options.keys()))
    return capsule_options.get(choice)


def create_capsule_ui() -> Optional[int]:
    st.subheader("Create a new capsule")
    with st.form("create_capsule_form"):
        title = st.text_input("Title", "Grandpa's Stories")
        description = st.text_area("Description", "Short description of this capsule")
        recipient = st.text_input("Recipient", "My family")
        delivery_date = st.date_input("Delivery date", value=datetime.utcnow().date() + timedelta(days=30))
        tags = st.text_input("Tags (comma separated)", "family, legacy")
        submitted = st.form_submit_button("Create capsule")
    if submitted:
        capsule_id = database.create_capsule(
            title=title,
            description=description,
            recipient=recipient,
            delivery_date=datetime.combine(delivery_date, datetime.min.time()),
            tags=[t.strip() for t in tags.split(",") if t.strip()],
        )
        st.success(f"Created capsule #{capsule_id}")
        return capsule_id
    return None


def upload_ui(capsule_id: int) -> None:
    st.subheader("Upload content")
    text_input = st.text_area("Paste a memory (text)")
    if st.button("Save text") and text_input.strip():
        database.add_asset(capsule_id, asset_type="text", content_text=text_input.strip())
        st.success("Saved text to capsule")

    file = st.file_uploader("Upload audio/image/document", type=["wav", "mp3", "m4a", "flac", "ogg", "png", "jpg", "jpeg", "pdf", "txt"])
    if file is not None:
        out_path = database.UPLOADS_DIR / f"capsule_{capsule_id}_{file.name}"
        with open(out_path, "wb") as f:
            f.write(file.getbuffer())
        content_text: Optional[str] = None
        if out_path.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            with st.spinner("Transcribing audio..."):
                content_text = transcribe_audio(str(out_path))
        database.add_asset(
            capsule_id,
            asset_type="audio" if content_text is not None else "file",
            filename=out_path.name,
            content_text=content_text,
        )
        st.success("File saved")



def analyze_ui(capsule_id: int) -> None:
    st.subheader("Analyze capsule")
    assets = database.get_assets_for_capsule(capsule_id)
    texts: List[str] = [a["content_text"] for a in assets if a["content_text"]]
    combined = "\n\n".join(texts)
    if st.button("Run analysis"):
        with st.spinner("Summarizing and scoring emotions..."):
            summary = summarize_text(combined, sentences=5) if combined else ""
            agg_scores = {}
            for t in texts:
                result = analyze_text_emotions(t)
                for k, v in result["scores"].items():  # type: ignore[index]
                    agg_scores[k] = agg_scores.get(k, 0.0) + float(v)
            total = sum(agg_scores.values())
            if total > 0:
                agg_scores = {k: round(v / total, 4) for k, v in agg_scores.items()}
            database.upsert_analysis(capsule_id, summary=summary, emotion_scores=agg_scores, themes=[])
            st.success("Analysis saved")

    analysis = database.get_analysis(capsule_id)
    if analysis:
        st.write("Summary:")
        st.info(analysis["summary"] or "(none)")
        st.write("Emotion scores:")
        st.json(json.loads(analysis["emotion_scores"]) if analysis["emotion_scores"] else {})



def delivery_ui(capsule_id: int) -> None:
    st.subheader("Schedule delivery")
    channel = st.selectbox("Channel", options=["log"])  # future: email
    scheduled_for = st.date_input("Scheduled for", value=datetime.utcnow().date() + timedelta(days=1))
    message = st.text_area("Optional message")
    if st.button("Schedule"):
        delivery_id = database.schedule_delivery(
            capsule_id=capsule_id,
            scheduled_for=datetime.combine(scheduled_for, datetime.min.time()),
            channel=channel,
            message=message or None,
        )
        st.success(f"Delivery scheduled #{delivery_id}")



def memory_book_ui(capsule_id: int) -> None:
    st.subheader("Memory Book")
    if st.button("Generate PDF"):
        with st.spinner("Generating memory book..."):
            path = generate_memory_book(capsule_id)
            st.success(f"Generated: {path.name}")
            with open(path, "rb") as f:
                st.download_button("Download PDF", data=f.read(), file_name=path.name, mime="application/pdf")



def main() -> None:
    ensure_db()
    st.title("LifeCache – AI-Powered Time Capsule")

    capsule_id = sidebar_capsules()

    st.sidebar.markdown("---")
    if st.sidebar.button("New capsule"):
        created = create_capsule_ui()
        if created:
            st.experimental_rerun()

    if capsule_id is None:
        st.info("Select or create a capsule to begin.")
        return

    upload_ui(capsule_id)
    analyze_ui(capsule_id)
    memory_book_ui(capsule_id)
    delivery_ui(capsule_id)


if __name__ == "__main__":
    main()
