from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class CourseInitResponse(BaseModel):
    course_id: str = Field(..., description="Unique ID for this course session")
    course_name: str
    semester: str
    chunks_indexed: int = Field(..., description="Number of text chunks stored in the vector DB")
    message: str

class ChatRequest(BaseModel):
    course_id: str = Field(..., description="Course session ID returned by /course/init")
    question: str  = Field(..., min_length=1, description="Student's question")

class ChatResponse(BaseModel):
    course_id: str
    question: str
    answer: str
    sources_used: int = Field(..., description="Number of syllabus chunks retrieved")

class MCQOption(BaseModel):
    A: str
    B: str
    C: str
    D: str

class MCQQuestion(BaseModel):
    question: str
    options: MCQOption
    answer: str = Field(..., description="Correct option key: A | B | C | D")

class QuizGenerateRequest(BaseModel):
    course_id:     str = Field(..., description="Course session ID")
    topic:         str = Field(..., min_length=1, description="Topic or chapter for the quiz")
    num_questions: int = Field(5, ge=1, le=20, description="Number of questions to generate")

class QuizGenerateResponse(BaseModel):
    quiz_id:   str
    course_id: str
    topic:     str
    questions: list[MCQQuestion]
    total:     int

class SubmitAnswerRequest(BaseModel):
    quiz_id:    str = Field(..., description="Quiz ID returned by /quiz/generate")
    q_index:    int = Field(..., ge=0, description="Zero-based question index")
    selected:   Optional[str] = Field(None, description="Selected option key: A | B | C | D. Null = skipped")

class AnswerFeedback(BaseModel):
    q_index:    int
    selected:   Optional[str]
    correct:    str
    is_correct: bool
    explanation: str

class QuizResultsRequest(BaseModel):
    quiz_id: str

class QuizResults(BaseModel):
    quiz_id:       str
    total:         int
    correct_count: int
    skipped_count: int
    percentage:    float
    grade:         str            # Pass | Fail
    grade_msg:     str
    breakdown:     list[AnswerFeedback]


class TTSRequest(BaseModel):
    text:     str  = Field(..., min_length=1, description="Text to convert to speech")
    lang:     str  = Field("en", description="Language code, e.g. 'en', 'ur'")
    slow:     bool = Field(False, description="Slow speech mode")

class TTSQuestionRequest(BaseModel):
    quiz_id:  str
    q_index:  int = Field(..., ge=0)
    lang:     str = Field("en")
    slow:     bool = Field(False)