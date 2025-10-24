from __future__ import annotations

from typing import Optional

from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer


def summarize_text(text: str, sentences: int = 5) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text.split()) <= sentences * 20:
        return text

    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LexRankSummarizer()
    summary_sentences = summarizer(parser.document, sentences)
    return " ".join(str(s) for s in summary_sentences)
