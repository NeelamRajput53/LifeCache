from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
ANALYSIS_DIR = DATA_DIR / "analysis"
DELIVERIES_DIR = DATA_DIR / "deliveries"
OUTPUT_DIR = DATA_DIR / "output"
TMP_DIR = DATA_DIR / "tmp"

for d in (DATA_DIR, UPLOADS_DIR, ANALYSIS_DIR, DELIVERIES_DIR, OUTPUT_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "lifecache.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with closing(_connect()) as conn, conn:  # type: ignore[call-arg]
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                recipient TEXT,
                delivery_date TEXT,
                tags TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capsule_id INTEGER NOT NULL,
                type TEXT NOT NULL, -- text | audio | image | document
                filename TEXT,
                content_text TEXT,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (capsule_id) REFERENCES capsules(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capsule_id INTEGER UNIQUE NOT NULL,
                summary TEXT,
                emotion_scores TEXT, -- JSON
                themes TEXT,         -- JSON
                created_at TEXT NOT NULL,
                FOREIGN KEY (capsule_id) REFERENCES capsules(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capsule_id INTEGER NOT NULL,
                status TEXT NOT NULL, -- scheduled | delivered | failed
                scheduled_for TEXT NOT NULL,
                delivered_at TEXT,
                channel TEXT NOT NULL, -- email | log
                recipient_email TEXT,
                message TEXT,
                token TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (capsule_id) REFERENCES capsules(id)
            )
            """
        )


# --- Capsule operations ---

def create_capsule(
    title: str,
    description: str = "",
    recipient: str = "",
    delivery_date: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
) -> int:
    initialize_database()
    now = datetime.utcnow().isoformat()
    tags_json = json.dumps(tags or [])
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO capsules (title, description, recipient, delivery_date, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                title,
                description,
                recipient,
                delivery_date.isoformat() if delivery_date else None,
                tags_json,
                now,
            ),
        )
        return int(cur.lastrowid)


def list_capsules() -> List[sqlite3.Row]:
    initialize_database()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM capsules ORDER BY created_at DESC"
        ).fetchall()
        return rows


def get_capsule(capsule_id: int) -> Optional[sqlite3.Row]:
    initialize_database()
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM capsules WHERE id = ?",
            (capsule_id,),
        ).fetchone()
        return row


# --- Asset operations ---

def add_asset(
    capsule_id: int,
    asset_type: str,
    filename: Optional[str] = None,
    content_text: Optional[str] = None,
) -> int:
    initialize_database()
    now = datetime.utcnow().isoformat()
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO assets (capsule_id, type, filename, content_text, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (capsule_id, asset_type, filename, content_text, now),
        )
        return int(cur.lastrowid)


def get_assets_for_capsule(capsule_id: int) -> List[sqlite3.Row]:
    initialize_database()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM assets WHERE capsule_id = ? ORDER BY uploaded_at ASC",
            (capsule_id,),
        ).fetchall()
        return rows


# --- Analysis operations ---

def upsert_analysis(
    capsule_id: int,
    summary: str,
    emotion_scores: Dict[str, float],
    themes: Optional[List[str]] = None,
) -> None:
    initialize_database()
    now = datetime.utcnow().isoformat()
    with closing(_connect()) as conn, conn:
        existing = conn.execute(
            "SELECT id FROM analysis WHERE capsule_id = ?",
            (capsule_id,),
        ).fetchone()
        payload = (
            summary,
            json.dumps(emotion_scores),
            json.dumps(themes or []),
            now,
            capsule_id,
        )
        if existing:
            conn.execute(
                "UPDATE analysis SET summary = ?, emotion_scores = ?, themes = ?, created_at = ? WHERE capsule_id = ?",
                payload,
            )
        else:
            conn.execute(
                "INSERT INTO analysis (summary, emotion_scores, themes, created_at, capsule_id) VALUES (?, ?, ?, ?, ?)",
                payload,
            )


def get_analysis(capsule_id: int) -> Optional[sqlite3.Row]:
    initialize_database()
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM analysis WHERE capsule_id = ?",
            (capsule_id,),
        ).fetchone()
        return row


# --- Delivery operations ---

def schedule_delivery(
    capsule_id: int,
    scheduled_for: datetime,
    channel: str = "log",
    recipient_email: Optional[str] = None,
    message: Optional[str] = None,
    token: Optional[str] = None,
) -> int:
    initialize_database()
    now = datetime.utcnow().isoformat()
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO deliveries (capsule_id, status, scheduled_for, channel, recipient_email, message, token, created_at)
            VALUES (?, 'scheduled', ?, ?, ?, ?, ?, ?)
            """,
            (
                capsule_id,
                scheduled_for.isoformat(),
                channel,
                recipient_email,
                message,
                token,
                now,
            ),
        )
        return int(cur.lastrowid)


def get_due_deliveries(now: Optional[datetime] = None) -> List[sqlite3.Row]:
    initialize_database()
    now_iso = (now or datetime.utcnow()).isoformat()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM deliveries WHERE status = 'scheduled' AND scheduled_for <= ? ORDER BY scheduled_for ASC",
            (now_iso,),
        ).fetchall()
        return rows


def update_delivery_status(delivery_id: int, status: str, delivered_at: Optional[datetime] = None) -> None:
    initialize_database()
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE deliveries SET status = ?, delivered_at = ? WHERE id = ?",
            (
                status,
                (delivered_at or datetime.utcnow()).isoformat() if status == "delivered" else None,
                delivery_id,
            ),
        )


# Utilities

def to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}
