from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from . import database


_LOG_PATH = (database.DELIVERIES_DIR / "deliveries.log")
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log(message: str) -> None:
    ts = datetime.utcnow().isoformat()
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def deliver_due() -> None:
    database.initialize_database()
    due = database.get_due_deliveries()
    for d in due:
        try:
            # For MVP we just log delivery. Email can be added later.
            capsule = database.get_capsule(d["capsule_id"]) if d else None
            title = capsule["title"] if capsule else "(unknown)"
            _log(
                f"Deliver capsule {d['capsule_id']} ({title}) via {d['channel']} to {d.get('recipient_email') or 'N/A'}: {d.get('message') or ''}"
            )
            database.update_delivery_status(int(d["id"]), status="delivered", delivered_at=datetime.utcnow())
        except Exception as exc:
            _log(f"Failed delivery id={d['id']}: {exc}")
            database.update_delivery_status(int(d["id"]), status="failed")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(deliver_due, "interval", minutes=1, id="deliver_due_job", replace_existing=True)
    scheduler.start()
    _log("Scheduler started")
    return scheduler
