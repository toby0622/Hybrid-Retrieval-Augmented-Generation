from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class DynamicSlotInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    slots: Dict[str, Optional[str]] = Field(default_factory=dict)

    _required_slots: List[str] = PrivateAttr(default_factory=list)
    _optional_slots: List[str] = PrivateAttr(default_factory=list)

    def set_slot(self, name: str, value: Optional[str]) -> None:
        self.slots[name] = value

    def get_slot(self, name: str) -> Optional[str]:
        return self.slots.get(name)

    def configure(self, required: List[str], optional: List[str]) -> None:
        self._required_slots = required
        self._optional_slots = optional

    def is_sufficient(self) -> bool:
        if not self._required_slots:
            return any(v for v in self.slots.values() if v)
        return all(self.slots.get(s) for s in self._required_slots)

    def get_missing_slots(self) -> List[str]:
        if not self._required_slots:
            return []
        return [s for s in self._required_slots if not self.slots.get(s)]

    def get_filled_slots(self) -> Dict[str, str]:
        return {k: v for k, v in self.slots.items() if v}

    def to_display_string(self) -> str:
        parts = []
        for name, value in self.slots.items():
            if value:
                display_name = name.replace("_", " ").title()
                parts.append(f"{display_name}: {value}")
        return "\n".join(parts) if parts else "No specific details provided yet."


class SlotInfo(BaseModel):
    service_name: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: Optional[str] = None
    environment: Optional[str] = None
    cluster: Optional[str] = None
    additional_context: Optional[str] = None

    def is_sufficient(self) -> bool:
        return bool(self.service_name or self.error_type)

    def get_missing_slots(self) -> List[str]:
        missing = []
        if not self.service_name:
            missing.append("service_name")
        if not self.error_type:
            missing.append("error_type")
        if not self.timestamp:
            missing.append("timestamp")
        return missing

    def to_dynamic(self) -> DynamicSlotInfo:
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


class RetrievalResult(BaseModel):
    source: Literal["graph", "vector", "skill"]
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    raw_data: Optional[Any] = None


class DiagnosticStep(BaseModel):
    id: str
    source: str
    title: str
    detail: str
    status: Literal["info", "warning", "error"]
    is_root: bool = False
    is_parallel: bool = False
    raw_content: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DiagnosticResponse(BaseModel):
    path: List[DiagnosticStep]
    suggestion: str
    confidence: float = 0.0


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    message_type: Literal["text", "reasoning", "diagnostic"] = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphState(TypedDict, total=False):
    query: str
    messages: List[Message]

    skill: str

    intent: str

    slots: Union[SlotInfo, DynamicSlotInfo]
    clarification_question: Optional[str]
    clarification_count: int

    awaiting_clarification: bool  # True when waiting for user clarification response
    original_query: Optional[str]  # Preserves original query during clarification flow
    clarification_response: Optional[
        str
    ]  # The user's response to a clarification question

    graph_results: List[RetrievalResult]
    vector_results: List[RetrievalResult]
    skill_results: List[RetrievalResult]
    aggregated_context: str

    reasoning_steps: List[str]
    diagnostic: Optional[DiagnosticResponse]
    response: str

    feedback: Literal["resolved", "more_info", "end", None]
    case_study_generated: bool

    error: Optional[str]
