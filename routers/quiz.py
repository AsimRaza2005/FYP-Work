"""
/quiz  — MCQ quiz endpoints.

POST /quiz/generate          Generate MCQs for a topic.
GET  /quiz/{quiz_id}         Get all questions for a quiz.
GET  /quiz/{quiz_id}/question/{q_index}   Get a single question.
POST /quiz/answer            Submit an answer for one question.
GET  /quiz/{quiz_id}/results Final scorecard.
DELETE /quiz/{quiz_id}       Remove a quiz session.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from schemas import (
    AnswerFeedback,
    MCQQuestion,
    MCQOption,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizResults,
    QuizResultsRequest,
    SubmitAnswerRequest,
)
from services import generate_mcqs, similarity_search
from store import QuizSession, course_store, quiz_store

router = APIRouter()

@router.post(
    "/generate",
    response_model=QuizGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate MCQ quiz questions",
    description=(
        "Searches the course vector store for context related to the given topic, "
        "then asks the LLM to generate the requested number of MCQs. "
        "Returns a **quiz_id** used to fetch questions and submit answers."
    ),
)
def generate_quiz(body: QuizGenerateRequest):
    session = _get_course_or_404(body.course_id)

    _, context = similarity_search(session.vector_store, body.topic, k=6)

    raw_questions = generate_mcqs(
        context       = context,
        topic         = body.topic,
        num_questions = body.num_questions,
        course_name   = session.course_name,
    )

    if not raw_questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM failed to generate valid MCQs. Try a different topic or retry.",
        )

    quiz_id = str(uuid.uuid4())
    quiz_store[quiz_id] = QuizSession(
        quiz_id   = quiz_id,
        course_id = body.course_id,
        topic     = body.topic,
        questions = raw_questions,
    )

    return QuizGenerateResponse(
        quiz_id   = quiz_id,
        course_id = body.course_id,
        topic     = body.topic,
        questions = [_to_mcq_schema(q) for q in raw_questions],
        total     = len(raw_questions),
    )


@router.get(
    "/{quiz_id}",
    response_model=QuizGenerateResponse,
    summary="Get all questions of a quiz",
)
def get_quiz(quiz_id: str):
    session = _get_quiz_or_404(quiz_id)
    return QuizGenerateResponse(
        quiz_id   = session.quiz_id,
        course_id = session.course_id,
        topic     = session.topic,
        questions = [_to_mcq_schema(q) for q in session.questions],
        total     = len(session.questions),
    )

@router.get(
    "/{quiz_id}/question/{q_index}",
    response_model=MCQQuestion,
    summary="Get a single question by index",
    description="Useful for one-question-at-a-time quiz flows.",
)
def get_question(quiz_id: str, q_index: int):
    session = _get_quiz_or_404(quiz_id)
    if q_index < 0 or q_index >= len(session.questions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question index {q_index} out of range (0–{len(session.questions)-1}).",
        )
    return _to_mcq_schema(session.questions[q_index])



@router.post(
    "/answer",
    response_model=AnswerFeedback,
    summary="Submit an answer for a question",
    description=(
        "Records the student's selected option (A/B/C/D) for the given question index. "
        "Returns immediate feedback: whether the answer is correct and the correct answer. "
        "Pass `selected: null` to mark the question as skipped."
    ),
)
def submit_answer(body: SubmitAnswerRequest):
    session = _get_quiz_or_404(body.quiz_id)

    if body.q_index < 0 or body.q_index >= len(session.questions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question index {body.q_index} is out of range.",
        )

    valid_keys = {"A", "B", "C", "D", None}
    if body.selected not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'selected' must be one of A, B, C, D or null. Got: '{body.selected}'.",
        )

    q          = session.questions[body.q_index]
    correct    = q["answer"]
    is_correct = body.selected == correct

    # Persist answer (allows overwriting if the student retries the same question)
    session.answers[body.q_index] = body.selected

    if body.selected is None:
        explanation = f"Question skipped. Correct answer: {correct} — {q['options'].get(correct, '')}"
    elif is_correct:
        explanation = "Correct! Well done."
    else:
        explanation = (
            f"Incorrect. The correct answer is {correct}: {q['options'].get(correct, '')}."
        )

    return AnswerFeedback(
        q_index    = body.q_index,
        selected   = body.selected,
        correct    = correct,
        is_correct = is_correct,
        explanation = explanation,
    )

@router.get(
    "/{quiz_id}/results",
    response_model=QuizResults,
    summary="Get final quiz scorecard",
    description=(
        "Calculates score, percentage, and grade based on all submitted answers. "
        "Unanswered questions count as incorrect."
    ),
)
def get_results(quiz_id: str):
    session = _get_quiz_or_404(quiz_id)
    total   = len(session.questions)

    correct_count = 0
    skipped_count = 0
    breakdown: list[AnswerFeedback] = []

    for i, q in enumerate(session.questions):
        selected   = session.answers.get(i)          # None if not submitted
        correct    = q["answer"]
        is_correct = selected == correct

        if selected is None:
            skipped_count += 1
            explanation = f"Not answered. Correct: {correct} — {q['options'].get(correct,'')}"
        elif is_correct:
            correct_count += 1
            explanation = "Correct!"
        else:
            explanation = (
                f"Incorrect. Correct answer: {correct} — {q['options'].get(correct, '')}."
            )

        breakdown.append(AnswerFeedback(
            q_index    = i,
            selected   = selected,
            correct    = correct,
            is_correct = is_correct,
            explanation = explanation,
        ))

    pct       = round(correct_count / total * 100, 1) if total else 0.0
    grade     = "Pass" if pct >= 50 else "Fail"
    grade_msg = (
        "Excellent!" if pct >= 70 else
        "Good effort!" if pct >= 40 else
        "Keep practising!"
    )

    return QuizResults(
        quiz_id       = quiz_id,
        total         = total,
        correct_count = correct_count,
        skipped_count = skipped_count,
        percentage    = pct,
        grade         = grade,
        grade_msg     = grade_msg,
        breakdown     = breakdown,
    )


# ─── POST /quiz/results (body version) ───────────────────────────────────────
# Alias — some frontend stacks prefer POST with body over GET with path param

@router.post(
    "/results",
    response_model=QuizResults,
    summary="Get final quiz scorecard (POST variant)",
)
def get_results_post(body: QuizResultsRequest):
    return get_results(body.quiz_id)


# ─── DELETE /quiz/{quiz_id} ───────────────────────────────────────────────────

@router.delete(
    "/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a quiz session",
)
def delete_quiz(quiz_id: str):
    _get_quiz_or_404(quiz_id)
    del quiz_store[quiz_id]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_course_or_404(course_id: str):
    session = course_store.get(course_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course session '{course_id}' not found. Call /course/init first.",
        )
    return session


def _get_quiz_or_404(quiz_id: str) -> QuizSession:
    session = quiz_store.get(quiz_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session '{quiz_id}' not found. Call /quiz/generate first.",
        )
    return session


def _to_mcq_schema(q: dict) -> MCQQuestion:
    opts = q.get("options", {})
    return MCQQuestion(
        question = q["question"],
        options  = MCQOption(
            A = opts.get("A", ""),
            B = opts.get("B", ""),
            C = opts.get("C", ""),
            D = opts.get("D", ""),
        ),
        answer = q.get("answer", ""),
    )