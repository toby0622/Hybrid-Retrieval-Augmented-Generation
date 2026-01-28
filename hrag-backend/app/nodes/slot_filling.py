"""
Slot Filling Node
Checks for required information and generates clarification questions
"""

from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from app.state import GraphState, SlotInfo


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.3,
    )


CLARIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a DevOps assistant gathering information about an incident.
The user reported an issue but some key details are missing.

Current known information:
{known_info}

Missing information needed:
{missing_slots}

Generate a friendly, concise question to gather ONE missing piece of information.
Focus on the most critical missing item first (usually service_name or error_type).
Keep the question under 50 words."""),
    ("human", "Original query: {query}")
])


MAX_CLARIFICATION_ROUNDS = 3


async def slot_check_node(state: GraphState) -> GraphState:
    """
    Slot Check Node
    
    Checks if we have sufficient information to proceed with retrieval.
    If not, generates a clarification question.
    """
    slots = state.get("slots", SlotInfo())
    query = state.get("query", "")
    clarification_count = state.get("clarification_count", 0)
    
    # Check if slots are sufficient or max rounds reached
    if slots.is_sufficient() or clarification_count >= MAX_CLARIFICATION_ROUNDS:
        return {
            **state,
            "clarification_question": None
        }
    
    # Generate clarification question
    missing = slots.get_missing_slots()
    
    if not missing:
        return {
            **state,
            "clarification_question": None
        }
    
    # Build known info string
    known_parts = []
    if slots.service_name:
        known_parts.append(f"Service: {slots.service_name}")
    if slots.error_type:
        known_parts.append(f"Error type: {slots.error_type}")
    if slots.timestamp:
        known_parts.append(f"Time: {slots.timestamp}")
    if slots.environment:
        known_parts.append(f"Environment: {slots.environment}")
    if slots.additional_context:
        known_parts.append(f"Context: {slots.additional_context}")
    
    known_info = "\n".join(known_parts) if known_parts else "No specific details provided yet."
    
    try:
        llm = get_llm()
        chain = CLARIFICATION_PROMPT | llm
        result = await chain.ainvoke({
            "query": query,
            "known_info": known_info,
            "missing_slots": ", ".join(missing)
        })
        clarification = result.content.strip()
    except Exception as e:
        # Fallback question
        if "service_name" in missing:
            clarification = "Which service or component is experiencing the issue?"
        elif "error_type" in missing:
            clarification = "What type of error or symptom are you seeing?"
        else:
            clarification = "Could you provide more details about the issue?"
    
    return {
        **state,
        "clarification_question": clarification,
        "clarification_count": clarification_count + 1
    }


def route_after_slot_check(state: GraphState) -> str:
    """Routing after slot check"""
    if state.get("clarification_question"):
        return "ask_clarification"
    return "retrieval"
