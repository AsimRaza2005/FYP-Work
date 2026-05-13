"""
Core AI services shared across all routers.
"""

from __future__ import annotations
import json
import os
from io import BytesIO

from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")


def extract_pdf_text(file_bytes_list: list[bytes]) -> str:
    """Extract raw text from a list of PDF byte blobs."""
    text = ""
    for file_bytes in file_bytes_list:
        reader = PdfReader(BytesIO(file_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def split_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.split_text(text)


def build_vector_store(chunks: list[str]) -> FAISS:
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return FAISS.from_texts(chunks, embedding=embeddings)


def similarity_search(vector_store: FAISS, query: str, k: int = 4) -> tuple[list, str]:
    """Return (docs, joined_context)."""
    docs = vector_store.similarity_search(query, k=k)
    context = "\n\n".join(d.page_content for d in docs)
    return docs, context


def get_llm():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

_QA_PROMPT = PromptTemplate(
    template="""You are an expert AI Professor for: {course_name} ({semester}).

Syllabus context:
{context}

Rules:
1. For policy / grading / schedule questions use ONLY the syllabus.
2. For quiz / test / viva / exam generation use your knowledge on syllabus topics.

Question: {question}
Answer:""",
    input_variables=["context", "question", "course_name", "semester"],
)

def answer_question(context: str, question: str, course_name: str, semester: str) -> str:
    chain = _QA_PROMPT | get_llm() | StrOutputParser()
    return chain.invoke({
        "context":     context,
        "question":    question,
        "course_name": course_name,
        "semester":    semester,
    })


_MCQ_PROMPT = PromptTemplate(
    template="""You are a quiz generator for the course: {course_name}.

Based on this content:
{context}

Generate exactly {num_questions} multiple-choice questions on the topic: "{topic}".

Return ONLY a valid JSON array, no markdown, no explanation:
[
  {{
    "question": "Question text?",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": ""
  }}
]""",
    input_variables=["context", "num_questions", "topic", "course_name"],
)

def generate_mcqs(
    context: str, topic: str, num_questions: int, course_name: str
) -> list[dict]:
    chain = _MCQ_PROMPT | get_llm() | StrOutputParser()
    raw = chain.invoke({
        "context":       context,
        "num_questions": num_questions,
        "topic":         topic,
        "course_name":   course_name,
    })
    return _parse_mcqs(raw)


def _parse_mcqs(raw: str) -> list[dict]:
    raw = raw.strip()
    s, e = raw.find("["), raw.rfind("]")
    if s == -1 or e == -1:
        return []
    try:
        return json.loads(raw[s : e + 1])
    except json.JSONDecodeError:
        return []