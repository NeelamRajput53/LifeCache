from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def transcribe_audio(audio_path: str, language: str = "en-US") -> Optional[str]:
    """Attempt to transcribe an audio file.

    - Tries PocketSphinx offline first if available.
    - If ALLOW_ONLINE_STT=1, will attempt Google Web Speech API.
    - Returns None if transcription unavailable.
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        return None

    try:
        import speech_recognition as sr
    except Exception:
        return None

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(str(audio_file)) as source:
            audio = recognizer.record(source)
    except Exception:
        return None

    # Try offline PocketSphinx
    try:
        return recognizer.recognize_sphinx(audio, language=language)  # type: ignore[arg-type]
    except Exception:
        pass

    # Optional online path
    if os.environ.get("ALLOW_ONLINE_STT") == "1":
        try:
            return recognizer.recognize_google(audio, language=language)
        except Exception:
            return None

    return None
