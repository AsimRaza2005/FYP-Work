"""
/tts  — Text-to-Speech endpoints.

POST /tts/generate           Convert any text → MP3 (base64 + raw download).
POST /tts/question           Convert a quiz question + options → MP3.
GET  /tts/question/{quiz_id}/{q_index}  Same via GET for easy browser testing.
"""

import base64
from io import BytesIO

from fastapi import APIRouter, HTTPException, Response, status
from gtts import gTTS

from schemas import TTSQuestionRequest, TTSRequest
from store import quiz_store

router = APIRouter()


# ─── Shared helper ────────────────────────────────────────────────────────────

def _synthesise(text: str, lang: str = "en", slow: bool = False) -> bytes:
    """Return raw MP3 bytes for the given text."""
    tts = gTTS(text=text, lang=lang, slow=slow)
    buf = BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def _build_question_text(q_index: int, q: dict) -> str:
    opts = ". ".join([f"Option {k}: {v}" for k, v in q.get("options", {}).items()])
    return f"Question {q_index + 1}. {q['question']}. Your options are: {opts}."


# ─── POST /tts/generate ───────────────────────────────────────────────────────

@router.post(
    "/generate",
    summary="Convert text to speech (MP3)",
    description=(
        "Accepts any text and returns the audio in two forms: "
        "a **base64-encoded** string (for embedding in JSON / HTML) "
        "and a raw **MP3 download** link via the `download` query parameter."
    ),
    responses={
        200: {
            "content": {"application/json": {}},
            "description": "JSON with base64 audio and metadata.",
        }
    },
)
def generate_tts(body: TTSRequest):
    try:
        mp3_bytes = _synthesise(body.text, lang=body.lang, slow=body.slow)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {exc}",
        )

    b64 = base64.b64encode(mp3_bytes).decode()

    return {
        "lang":        body.lang,
        "slow":        body.slow,
        "char_count":  len(body.text),
        "audio_base64": b64,
        "audio_data_url": f"data:audio/mp3;base64,{b64}",
        "note": "Use audio_data_url as the src for an <audio> element.",
    }


# ─── POST /tts/generate/download ─────────────────────────────────────────────

@router.post(
    "/generate/download",
    summary="Download MP3 file for given text",
    response_class=Response,
)
def generate_tts_download(body: TTSRequest):
    try:
        mp3_bytes = _synthesise(body.text, lang=body.lang, slow=body.slow)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {exc}",
        )

    return Response(
        content      = mp3_bytes,
        media_type   = "audio/mpeg",
        headers      = {"Content-Disposition": "attachment; filename=speech.mp3"},
    )


# ─── POST /tts/question ───────────────────────────────────────────────────────

@router.post(
    "/question",
    summary="Convert a quiz question + options to speech",
    description=(
        "Given a quiz_id and q_index, builds the speech text "
        "(question + all four options) and returns an MP3 as base64."
    ),
)
def question_tts(body: TTSQuestionRequest):
    session = _get_quiz_or_404(body.quiz_id)

    if body.q_index < 0 or body.q_index >= len(session.questions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question index {body.q_index} out of range.",
        )

    q    = session.questions[body.q_index]
    text = _build_question_text(body.q_index, q)

    try:
        mp3_bytes = _synthesise(text, lang=body.lang, slow=body.slow)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {exc}",
        )

    b64 = base64.b64encode(mp3_bytes).decode()

    return {
        "quiz_id":    body.quiz_id,
        "q_index":    body.q_index,
        "text":       text,
        "audio_base64":   b64,
        "audio_data_url": f"data:audio/mp3;base64,{b64}",
    }


# ─── GET /tts/question/{quiz_id}/{q_index} ────────────────────────────────────

@router.get(
    "/question/{quiz_id}/{q_index}",
    summary="Download question MP3 directly (browser-friendly)",
    response_class=Response,
)
def question_tts_download(quiz_id: str, q_index: int, lang: str = "en", slow: bool = False):
    session = _get_quiz_or_404(quiz_id)

    if q_index < 0 or q_index >= len(session.questions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question index {q_index} out of range.",
        )

    q    = session.questions[q_index]
    text = _build_question_text(q_index, q)

    try:
        mp3_bytes = _synthesise(text, lang=lang, slow=slow)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {exc}",
        )

    return Response(
        content    = mp3_bytes,
        media_type = "audio/mpeg",
        headers    = {"Content-Disposition": f"inline; filename=question_{q_index}.mp3"},
    )


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_quiz_or_404(quiz_id: str):
    session = quiz_store.get(quiz_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz '{quiz_id}' not found. Call /quiz/generate first.",
        )
    return session