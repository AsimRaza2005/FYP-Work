"""
/chat  — Syllabus Q&A endpoints.

POST /chat/ask      Ask a question; get an AI answer grounded in the syllabus.
GET  /chat/history  Retrieve conversation history for a course session.
DELETE /chat/history Clear history.
"""

from fastapi import APIRouter, HTTPException, status

from schemas import ChatRequest, ChatResponse
from services import answer_question, similarity_search
from store import course_store

router = APIRouter()

# Simple in-memory chat history per course: { course_id -> [{"role", "content"}] }
_history: dict[str, list[dict]] = {}


# ─── POST /chat/ask ───────────────────────────────────────────────────────────

@router.post(
    "/ask",
    response_model=ChatResponse,
    summary="Ask a question about the syllabus",
    description=(
        "Performs a similarity search over the course vector store to retrieve "
        "relevant syllabus chunks, then asks the LLM to answer using those chunks "
        "as context. The answer is also appended to the in-memory chat history."
    ),
)
def ask(body: ChatRequest):
    session = _get_course_or_404(body.course_id)

    # Retrieve relevant chunks
    docs, context = similarity_search(session.vector_store, body.question, k=4)

    # Generate answer
    answer = answer_question(
        context     = context,
        question    = body.question,
        course_name = session.course_name,
        semester    = session.semester,
    )

    # Persist to history
    hist = _history.setdefault(body.course_id, [])
    hist.append({"role": "user",      "content": body.question})
    hist.append({"role": "assistant", "content": answer})

    return ChatResponse(
        course_id    = body.course_id,
        question     = body.question,
        answer       = answer,
        sources_used = len(docs),
    )


# ─── GET /chat/history ────────────────────────────────────────────────────────

@router.get(
    "/history/{course_id}",
    summary="Get chat history for a course session",
)
def get_history(course_id: str):
    _get_course_or_404(course_id)
    return {
        "course_id": course_id,
        "history":   _history.get(course_id, []),
        "total_messages": len(_history.get(course_id, [])),
    }


# ─── DELETE /chat/history ─────────────────────────────────────────────────────

@router.delete(
    "/history/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear chat history for a course session",
)
def clear_history(course_id: str):
    _get_course_or_404(course_id)
    _history[course_id] = []


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_course_or_404(course_id: str):
    session = course_store.get(course_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course session '{course_id}' not found. Call /course/init first.",
        )
    return session