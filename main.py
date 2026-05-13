"""
╔══════════════════════════════════════════════════════════╗
║       AI Course Assistant — FastAPI Backend              ║
║                                                          ║
║  Base URL : http://localhost:8000                        ║
║  Docs     : http://localhost:8000/docs  (Swagger UI)     ║
║  ReDoc    : http://localhost:8000/redoc                  ║
╚══════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import course, chat, quiz, tts

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Course Assistant API",
    description=(
        "FastAPI backend for the AI Syllabus & Course Assistant. "
        "Handles PDF ingestion, vector search, LLM Q&A, MCQ generation, "
        "quiz scoring, and text-to-speech."
    ),
    version="1.0.0",
    contact={"name": "Course Assistant Team"},
)

# # ─── CORS (allow Streamlit / any frontend on localhost) ───────────────────────

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],        # tighten in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(course.router, prefix="/course", tags=["Course Setup"])
app.include_router(chat.router,   prefix="/chat",   tags=["Chat / Q&A"])
app.include_router(quiz.router,   prefix="/quiz",   tags=["MCQ Quiz"])
app.include_router(tts.router,    prefix="/tts",    tags=["Text-to-Speech"])

# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "AI Course Assistant API is running 🎓"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}