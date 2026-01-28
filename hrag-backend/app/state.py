"""
HRAG LangGraph State Definitions
Defines the state schema that flows through the graph
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SlotInfo(BaseModel):
    """Information slots extracted from user query"""
    service_name: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: Optional[str] = None
    environment: Optional[str] = None
    cluster: Optional[str] = None
    additional_context: Optional[str] = None
    
    def is_sufficient(self) -> bool:
        """Check if we have minimum required information"""
        return bool(self.service_name or self.error_type)
    
    def get_missing_slots(self) -> List[str]:
        """Get list of valuable missing slots"""
        missing = []
        if not self.service_name:
            missing.append("service_name")
        if not self.error_type:
            missing.append("error_type")
        if not self.timestamp:
            missing.append("timestamp")
        return missing


class RetrievalResult(BaseModel):
    """Result from a retrieval source"""
    source: Literal["graph", "vector", "mcp_tool"]
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    raw_data: Optional[Any] = None


class DiagnosticStep(BaseModel):
    """A step in the diagnostic path"""
    id: str
    source: str
    title: str
    detail: str
    status: Literal["info", "warning", "error"]
    is_root: bool = False
    is_parallel: bool = False
    raw_content: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticResponse(BaseModel):
    """Complete diagnostic response"""
    path: List[DiagnosticStep]
    suggestion: str
    confidence: float = 0.0


class Message(BaseModel):
    """Chat message"""
    role: Literal["user", "assistant", "system"]
    content: str
    message_type: Literal["text", "reasoning", "diagnostic"] = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphState(TypedDict, total=False):
    """
    The state that flows through the LangGraph.
    All nodes read from and write to this state.
    """
    # Input
    query: str
    messages: List[Message]
    
    # Intent Classification (Input Guard)
    intent: Literal["chat", "incident", "end"]
    
    # Slot Filling
    slots: SlotInfo
    clarification_question: Optional[str]
    clarification_count: int
    
    # Retrieval Results
    graph_results: List[RetrievalResult]
    vector_results: List[RetrievalResult]
    mcp_results: List[RetrievalResult]
    aggregated_context: str
    
    # Reasoning & Response
    reasoning_steps: List[str]
    diagnostic: Optional[DiagnosticResponse]
    response: str
    
    # Feedback Loop
    feedback: Literal["resolved", "more_info", "end", None]
    case_study_generated: bool
    
    # Error Handling
    error: Optional[str]
