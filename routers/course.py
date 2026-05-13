"""
/course  — Course setup endpoints.

POST /course/init   Upload syllabus PDFs, build vector store, return course_id.
GET  /course/{id}   Get course metadata.
DELETE /course/{id} Remove course session.
"""

import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from schemas import CourseInitResponse
from services import build_vector_store, extract_pdf_text, split_text
from store import CourseSession, course_store

router = APIRouter()


# ─── POST /course/init ────────────────────────────────────────────────────────

@router.post(
    "/init",
    response_model=CourseInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload syllabus PDFs and initialise a course session",
    description=(
        "Upload one or more syllabus PDF files along with course metadata. "
        "The backend extracts text, splits it into chunks, builds a FAISS "
        "vector store, and returns a **course_id** to use in all subsequent calls."
    ),
)
async def init_course(
    course_name: str      = Form(..., description="Name of the course, e.g. 'Intro to Python'"),
    semester:    str      = Form("Not Specified", description="Semester / section label"),
    files:       list[UploadFile] = File(..., description="One or more syllabus PDF files"),
):
    # Validate file types
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{f.filename}' is not a PDF.",
            )

    # Read all PDFs into memory
    file_bytes_list = [await f.read() for f in files]

    # Extract text → split → embed → vector store
    raw_text = extract_pdf_text(file_bytes_list)
    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any text from the uploaded PDFs.",
        )

    chunks       = split_text(raw_text)
    vector_store = build_vector_store(chunks)
    course_id    = str(uuid.uuid4())

    course_store[course_id] = CourseSession(
        course_id     = course_id,
        course_name   = course_name,
        semester      = semester,
        vector_store  = vector_store,
        chunks_indexed = len(chunks),
    )

    return CourseInitResponse(
        course_id      = course_id,
        course_name    = course_name,
        semester       = semester,
        chunks_indexed = len(chunks),
        message        = "Course initialised successfully. Use course_id in further requests.",
    )


# ─── GET /course/{course_id} ──────────────────────────────────────────────────

@router.get(
    "/{course_id}",
    summary="Get course session metadata",
)
def get_course(course_id: str):
    session = _get_or_404(course_id)
    return {
        "course_id":      session.course_id,
        "course_name":    session.course_name,
        "semester":       session.semester,
        "chunks_indexed": session.chunks_indexed,
    }


# ─── DELETE /course/{course_id} ───────────────────────────────────────────────

@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a course session",
)
def delete_course(course_id: str):
    _get_or_404(course_id)
    del course_store[course_id]


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_or_404(course_id: str) -> CourseSession:
    session = course_store.get(course_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course session '{course_id}' not found. Please call /course/init first.",
        )
    return session