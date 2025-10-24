from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import database
from .utils.pdf_generator import generate_memory_book
from ..nlp.emotion import analyze_text_emotions, cluster_messages
from ..nlp.summarizer import summarize_text
from ..nlp.stt import transcribe_audio

app = FastAPI(title="LifeCache API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CapsuleCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    recipient: Optional[str] = ""
    delivery_date: Optional[str] = None  # ISO string
    tags: Optional[List[str]] = None


@app.on_event("startup")
def on_startup() -> None:
    database.initialize_database()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/capsules")
def list_capsules_endpoint() -> List[Dict[str, object]]:
    rows = database.list_capsules()
    return [database.to_dict(r) for r in rows]


@app.post("/capsules")
def create_capsule_endpoint(payload: CapsuleCreate) -> Dict[str, object]:
    delivery_dt = (
        datetime.fromisoformat(payload.delivery_date) if payload.delivery_date else None
    )
    capsule_id = database.create_capsule(
        title=payload.title,
        description=payload.description or "",
        recipient=payload.recipient or "",
        delivery_date=delivery_dt,
        tags=payload.tags or [],
    )
    return {"capsule_id": capsule_id}


@app.post("/capsules/{capsule_id}/upload-text")
def upload_text(capsule_id: int, text: str = Form(...)) -> Dict[str, object]:
    if database.get_capsule(capsule_id) is None:
        raise HTTPException(404, "Capsule not found")
    asset_id = database.add_asset(capsule_id, asset_type="text", content_text=text)
    return {"asset_id": asset_id}


@app.post("/capsules/{capsule_id}/upload-file")
def upload_file(capsule_id: int, file: UploadFile = File(...)) -> Dict[str, object]:
    if database.get_capsule(capsule_id) is None:
        raise HTTPException(404, "Capsule not found")
    filename = file.filename or "uploaded.bin"
    out_path = database.UPLOADS_DIR / f"capsule_{capsule_id}_{filename}"
    with open(out_path, "wb") as f:
        f.write(file.file.read())
    # Try to transcribe audio types
    content_text: Optional[str] = None
    if filename.lower().endswith((".wav", ".mp3", ".m4a", ".flac", ".ogg")):
        try:
            content_text = transcribe_audio(str(out_path))
        except Exception:
            content_text = None
    asset_id = database.add_asset(
        capsule_id, asset_type="audio" if content_text is not None else "file", filename=str(out_path.name), content_text=content_text
    )
    return {"asset_id": asset_id, "transcribed": bool(content_text)}


@app.post("/capsules/{capsule_id}/analyze")
def analyze_capsule(capsule_id: int) -> Dict[str, object]:
    if database.get_capsule(capsule_id) is None:
        raise HTTPException(404, "Capsule not found")
    assets = database.get_assets_for_capsule(capsule_id)
    texts: List[str] = [a["content_text"] for a in assets if a["content_text"]]
    combined = "\n\n".join(texts)
    summary = summarize_text(combined, sentences=5) if combined else ""
    # Aggregate emotion scores across assets
    agg_scores: Dict[str, float] = {}
    for t in texts:
        result = analyze_text_emotions(t)
        for k, v in result["scores"].items():  # type: ignore[index]
            agg_scores[k] = agg_scores.get(k, 0.0) + float(v)
    total = sum(agg_scores.values())
    if total > 0:
        agg_scores = {k: round(v / total, 4) for k, v in agg_scores.items()}

    labels = cluster_messages(texts, k=4) if texts else []
    theme_map: Dict[int, List[str]] = {}
    for idx, label in enumerate(labels):
        theme_map.setdefault(label, []).append(texts[idx])
    themes = [f"cluster_{i}" for i in sorted(theme_map.keys())]

    database.upsert_analysis(capsule_id, summary=summary, emotion_scores=agg_scores, themes=themes)
    return {"summary": summary, "emotion_scores": agg_scores, "themes": themes}


@app.get("/capsules/{capsule_id}/memory-book")
def memory_book(capsule_id: int) -> Dict[str, object]:
    path = generate_memory_book(capsule_id)
    return {"pdf_path": str(path)}
