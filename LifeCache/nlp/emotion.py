from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


_ANALYZER = SentimentIntensityAnalyzer()

_KEYWORDS: Dict[str, List[str]] = {
    "joy": ["happy", "joy", "smile", "grateful", "blessed", "proud", "celebrate"],
    "sorrow": ["sad", "loss", "miss", "cry", "grief", "sorry", "alone"],
    "advice": ["remember", "always", "should", "lesson", "advice", "teach"],
    "legacy": ["legacy", "remember me", "after i'm gone", "future", "values", "family"],
    "gratitude": ["thank", "thanks", "grateful", "appreciate"],
    "anger": ["angry", "mad", "furious", "upset", "annoyed"],
    "fear": ["fear", "worry", "anxious", "afraid", "scared"],
    "love": ["love", "dear", "beloved", "daughter", "son", "wife", "husband"],
}


def _keyword_score(text: str) -> Dict[str, float]:
    scores: Dict[str, float] = defaultdict(float)
    lowered = text.lower()
    for emotion, kws in _KEYWORDS.items():
        for kw in kws:
            # simple word boundary match
            if re.search(rf"\b{re.escape(kw)}\b", lowered):
                scores[emotion] += 1.0
    return dict(scores)


def analyze_text_emotions(text: str) -> Dict[str, object]:
    text = (text or "").strip()
    if not text:
        return {"dominant_emotion": "neutral", "scores": {}, "sentiment": {"compound": 0.0}}

    vs = _ANALYZER.polarity_scores(text)

    # Seed from keywords
    scores = _keyword_score(text)

    # Blend VADER into emotion buckets heuristically
    compound = float(vs.get("compound", 0.0))
    pos = float(vs.get("pos", 0.0))
    neg = float(vs.get("neg", 0.0))
    neu = float(vs.get("neu", 0.0))

    # Positive sentiment nudges joy/gratitude/love
    if compound > 0:
        scores["joy"] = scores.get("joy", 0.0) + compound * 2.0
        scores["gratitude"] = scores.get("gratitude", 0.0) + pos
        scores["love"] = scores.get("love", 0.0) + pos * 0.5
    elif compound < 0:
        # Negative sentiment nudges sorrow/fear/anger
        scores["sorrow"] = scores.get("sorrow", 0.0) + (-compound) * 2.0
        scores["fear"] = scores.get("fear", 0.0) + neg
        scores["anger"] = scores.get("anger", 0.0) + neg * 0.5

    # Normalize to [0, 1]
    total = sum(scores.values())
    if total > 0:
        for k in list(scores.keys()):
            scores[k] = round(scores[k] / total, 4)

    dominant = max(scores.items(), key=lambda kv: kv[1])[0] if scores else "neutral"
    return {
        "dominant_emotion": dominant,
        "scores": scores,
        "sentiment": vs,
    }


def cluster_messages(messages: List[str], k: int = 4) -> List[int]:
    """Lightweight clustering of short messages using TF-IDF + KMeans.
    Returns cluster labels for input messages.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.feature_extraction.text import TfidfVectorizer
    except Exception:  # pragma: no cover - optional dependency
        return [0 for _ in messages]

    docs = [m or "" for m in messages]
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(docs)
    k = max(1, min(k, len(docs)))
    model = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = model.fit_predict(X)
    return labels.tolist()
