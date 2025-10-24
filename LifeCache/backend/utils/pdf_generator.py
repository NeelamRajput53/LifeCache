from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from fpdf import FPDF
import matplotlib.pyplot as plt

from .. import database


class MemoryBookPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "LifeCache Memory Book", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _plot_emotions(emotion_scores: Dict[str, float], out_path: Path) -> None:
    if not emotion_scores:
        return
    labels = list(emotion_scores.keys())
    values = [emotion_scores[k] for k in labels]
    plt.figure(figsize=(6, 3))
    plt.bar(labels, values, color="#6c8ff5")
    plt.xticks(rotation=30)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


def generate_memory_book(capsule_id: int) -> Path:
    database.initialize_database()
    base_dir = database.BASE_DIR
    output_dir = database.OUTPUT_DIR
    tmp_dir = database.TMP_DIR

    capsule = database.get_capsule(capsule_id)
    assets = database.get_assets_for_capsule(capsule_id)
    analysis = database.get_analysis(capsule_id)

    if capsule is None:
        raise ValueError(f"Capsule {capsule_id} not found")

    pdf = MemoryBookPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cover
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, f"{capsule['title']}", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", size=12)
    if capsule["recipient"]:
        pdf.multi_cell(0, 8, f"For: {capsule['recipient']}")
    if capsule["delivery_date"]:
        pdf.multi_cell(0, 8, f"Scheduled for: {capsule['delivery_date']}")
    if capsule["description"]:
        pdf.ln(4)
        pdf.multi_cell(0, 7, capsule["description"]) 

    # Summary
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    summary_text = analysis["summary"] if analysis and analysis["summary"] else "No summary available yet."
    pdf.multi_cell(0, 7, summary_text)

    # Quotes / excerpts
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, "Selected Excerpts", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    excerpts_added = 0
    for a in assets:
        text = (a["content_text"] or "").strip()
        if not text:
            continue
        excerpt = (text[:280] + "...") if len(text) > 280 else text
        pdf.multi_cell(0, 6, f"• {excerpt}")
        pdf.ln(1)
        excerpts_added += 1
        if excerpts_added >= 10:
            break

    # Emotion chart
    if analysis and analysis.get("emotion_scores"):
        try:
            scores: Dict[str, float] = json.loads(analysis["emotion_scores"])  # type: ignore
        except Exception:
            scores = {}
        if scores:
            chart_path = tmp_dir / f"emotions_capsule_{capsule_id}.png"
            _plot_emotions(scores, chart_path)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Emotion Profile", new_x="LMARGIN", new_y="NEXT")
            pdf.image(str(chart_path), w=180)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_pdf_path = output_dir / f"memory_book_capsule_{capsule_id}.pdf"
    pdf.output(str(out_pdf_path))
    return out_pdf_path
