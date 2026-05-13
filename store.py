"""
In-memory session store.

Holds:
  - course_store  : { course_id -> CourseSession }
  - quiz_store    : { quiz_id   -> QuizSession   }

For production, replace with Redis or a database.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class CourseSession:
    course_id:   str
    course_name: str
    semester:    str
    vector_store: Any          # FAISS instance
    chunks_indexed: int = 0


@dataclass
class QuizSession:
    quiz_id:   str
    course_id: str
    topic:     str
    questions: list[dict]                       # raw MCQ dicts from LLM
    answers:   dict[int, Optional[str]] = field(default_factory=dict)
    # answers[q_index] = "A" | "B" | "C" | "D" | None (skipped)


course_store: dict[str, CourseSession] = {}
quiz_store:   dict[str, QuizSession]   = {}