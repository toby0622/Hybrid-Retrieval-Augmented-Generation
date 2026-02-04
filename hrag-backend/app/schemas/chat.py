from typing import List, Optional
from pydantic import BaseModel

from app.state import DiagnosticResponse

class ReasoningStep(BaseModel):
    id: str
    label: str
    status: str = "pending"


class ChatRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None
    feedback: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    intent: Optional[str] = None
    response_type: str = "text"
    reasoning_steps: Optional[List[ReasoningStep]] = None
    diagnostic: Optional[DiagnosticResponse] = None
    clarification_question: Optional[str] = None
