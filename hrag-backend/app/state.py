"""
HRAG LangGraph State Definitions
Defines the state schema that flows through the graph

Supports dynamic domain configuration - slots and intents are defined per domain.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, Field


# =============================================================================
# Dynamic Slot System
# =============================================================================


class DynamicSlotInfo(BaseModel):
    """
    Dynamic information slots extracted from user query.
    Slot names and requirements are defined by the active domain config.
    """

    slots: Dict[str, Optional[str]] = Field(default_factory=dict)
    
    # Cached domain config reference (not serialized)
    _required_slots: List[str] = []
    _optional_slots: List[str] = []

    def set_slot(self, name: str, value: Optional[str]) -> None:
        """Set a slot value."""
        self.slots[name] = value

    def get_slot(self, name: str) -> Optional[str]:
        """Get a slot value."""
        return self.slots.get(name)

    def configure(self, required: List[str], optional: List[str]) -> None:
        """Configure which slots are required/optional (from domain config)."""
        self._required_slots = required
        self._optional_slots = optional

    def is_sufficient(self) -> bool:
        """Check if we have minimum required information."""
        if not self._required_slots:
            # No config = any non-empty slot is sufficient
            return any(v for v in self.slots.values() if v)
        return all(self.slots.get(s) for s in self._required_slots)

    def get_missing_slots(self) -> List[str]:
        """Get list of missing required slots."""
        if not self._required_slots:
            return []
        return [s for s in self._required_slots if not self.slots.get(s)]

    def get_filled_slots(self) -> Dict[str, str]:
        """Get all filled slots."""
        return {k: v for k, v in self.slots.items() if v}

    def to_display_string(self) -> str:
        """Format slots for display in prompts."""
        parts = []
        for name, value in self.slots.items():
            if value:
                display_name = name.replace("_", " ").title()
                parts.append(f"{display_name}: {value}")
        return "\n".join(parts) if parts else "No specific details provided yet."

    class Config:
        # Allow setting private attributes
        underscore_attrs_are_private = True


# =============================================================================
# Legacy SlotInfo (Deprecated - for backward compatibility)
# =============================================================================


class SlotInfo(BaseModel):
    """
    DEPRECATED: Use DynamicSlotInfo instead.
    Kept for backward compatibility with existing code.
    """

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

    def to_dynamic(self) -> DynamicSlotInfo:
        """Convert to DynamicSlotInfo."""
        dynamic = DynamicSlotInfo()
        dynamic.slots = {
            "service_name": self.service_name,
            "error_type": self.error_type,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "cluster": self.cluster,
            "additional_context": self.additional_context,
        }
        dynamic.configure(
            required=["service_name", "error_type"],
            optional=["timestamp", "environment", "cluster", "additional_context"],
        )
        return dynamic


# =============================================================================
# Retrieval & Response Models
# =============================================================================


class RetrievalResult(BaseModel):
    """Result from a retrieval source"""

    source: Literal["graph", "vector", "mcp_tool"]
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    raw_data: Optional[Any] = None


class DiagnosticStep(BaseModel):
    """A step in the diagnostic/analysis path"""

    id: str
    source: str
    title: str
    detail: str
    status: Literal["info", "warning", "error"]
    is_root: bool = False
    is_parallel: bool = False
    raw_content: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticResponse(BaseModel):
    """Complete diagnostic/analysis response"""

    path: List[DiagnosticStep]
    suggestion: str
    confidence: float = 0.0


class Message(BaseModel):
    """Chat message"""

    role: Literal["user", "assistant", "system"]
    content: str
    message_type: Literal["text", "reasoning", "diagnostic"] = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Graph State
# =============================================================================


class GraphState(TypedDict, total=False):
    """
    The state that flows through the LangGraph.
    All nodes read from and write to this state.
    
    Designed to be domain-agnostic - intent types and slot names
    are defined by the active domain configuration.
    """

    # Input
    query: str
    messages: List[Message]
    
    # Active domain (determines behavior)
    domain: str

    # Intent Classification (Input Guard)
    # Dynamic: actual valid values depend on domain config
    intent: str

    # Slot Filling (Dynamic)
    slots: Union[SlotInfo, DynamicSlotInfo]  # Support both for migration
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

