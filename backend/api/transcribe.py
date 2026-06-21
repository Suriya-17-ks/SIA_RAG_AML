"""
Speech-to-Text endpoint using Groq Whisper API.
Accepts audio file upload, returns transcription.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from backend.config.settings import settings
import logging
import tempfile
import os

logger = logging.getLogger(__name__)
router = APIRouter()


class TranscriptionResponse(BaseModel):
    text: str
    language: str = "en"
    duration: float = 0.0


@router.post("/", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio using Groq's Whisper API (whisper-large-v3-turbo).
    Accepts: WAV, MP3, MP4, WEBM, OGG, FLAC (max 25MB).
    """
    # Validate file size (25MB limit for Groq)
    MAX_SIZE = 25 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large. Maximum 25MB.")

    # Validate we have a Groq API key
    api_key = settings.groq_api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured for Whisper.")

    # Save to a temp file (Groq SDK needs a file path)
    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(content)
        tmp.flush()
        tmp.close()

        # Call Groq Whisper API
        from groq import Groq
        client = Groq(api_key=api_key)

        with open(tmp.name, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(file.filename or "audio.webm", audio_file.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                language="en",
            )

        text = transcription.text or ""
        duration = getattr(transcription, "duration", 0.0) or 0.0
        language = getattr(transcription, "language", "en") or "en"

        logger.info(f"[transcribe] Transcribed {len(content)} bytes → {len(text)} chars ({duration:.1f}s)")

        return TranscriptionResponse(
            text=text.strip(),
            language=language,
            duration=duration,
        )

    except Exception as exc:
        logger.error(f"[transcribe] Whisper error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
