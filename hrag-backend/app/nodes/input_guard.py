"""
Input Guard Node
Routes user input: chat / incident query / end conversation
"""

from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from app.state import GraphState, SlotInfo


# Initialize LLM (LM Studio compatible via OpenAI API)
def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.1,
    )


CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an intent classifier for a DevOps incident response system.
Classify the user's message into one of these categories:

- "incident": The user is reporting an issue, asking about errors, troubleshooting, or investigating a problem.
  Examples: "Why is the API slow?", "Payment service is down", "Error 500 in production"
  
- "chat": General greetings, help requests, or unrelated conversation.
  Examples: "Hello", "Who are you?", "What can you do?"
  
- "end": User wants to end the conversation.
  Examples: "Thanks, that's all", "Goodbye", "Done"

Respond with ONLY the category word: incident, chat, or end"""),
    ("human", "{query}")
])


SLOT_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are extracting structured information from a DevOps incident query.
Extract the following fields if present (respond in JSON format):

{{
  "service_name": "name of the affected service or null",
  "error_type": "type of error (timeout, crash, slow, etc.) or null", 
  "timestamp": "when the issue occurred or null",
  "environment": "prod, staging, dev, or null",
  "cluster": "cluster name or null",
  "additional_context": "any other relevant details or null"
}}

Only extract information that is explicitly mentioned. Do not infer or guess."""),
    ("human", "{query}")
])


async def input_guard_node(state: GraphState) -> GraphState:
    """
    Input Guardrails Node
    
    1. Classifies user intent (chat/incident/end)
    2. For incident queries, extracts initial slots
    """
    query = state.get("query", "")
    
    if not query.strip():
        return {
            **state,
            "intent": "chat",
            "response": "Please provide a message."
        }
    
    llm = get_llm()
    
    # Step 1: Classify intent
    try:
        classification_chain = CLASSIFICATION_PROMPT | llm
        result = await classification_chain.ainvoke({"query": query})
        intent_raw = result.content.strip().lower()
        
        # Map to valid intent
        if "incident" in intent_raw:
            intent: Literal["chat", "incident", "end"] = "incident"
        elif "end" in intent_raw:
            intent = "end"
        else:
            intent = "chat"
            
    except Exception as e:
        # Fallback to simple keyword matching
        lower_query = query.lower()
        if any(kw in lower_query for kw in ["error", "slow", "down", "fail", "issue", "problem", "timeout", "crash"]):
            intent = "incident"
        elif any(kw in lower_query for kw in ["bye", "thanks", "done", "goodbye"]):
            intent = "end"
        else:
            intent = "chat"
    
    # Step 2: For incidents, extract slots
    slots = SlotInfo()
    if intent == "incident":
        try:
            extraction_chain = SLOT_EXTRACTION_PROMPT | llm
            result = await extraction_chain.ainvoke({"query": query})
            
            # Parse JSON response
            import json
            content = result.content.strip()
            # Handle markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            slot_data = json.loads(content)
            slots = SlotInfo(**{k: v for k, v in slot_data.items() if v is not None})
            
        except Exception as e:
            # Enhanced fallback extraction with regex/keyword matching
            slots = _extract_slots_fallback(query)
    
    return {
        **state,
        "intent": intent,
        "slots": slots,
        "clarification_count": state.get("clarification_count", 0)
    }


def _extract_slots_fallback(query: str) -> SlotInfo:
    """Fallback slot extraction when LLM is unavailable."""
    import re
    
    lower_query = query.lower()
    
    # Known service names (add more as needed)
    known_services = [
        "PaymentService", "OrderService", "UserService", 
        "NotificationService", "InventoryService",
        "payment-service", "order-service", "user-service",
        "payment", "order", "user", "inventory", "notification",
        "api", "gateway", "auth", "database", "redis", "kafka"
    ]
    
    service_name = None
    for svc in known_services:
        if svc.lower() in lower_query:
            service_name = svc
            break
    
    # Error types
    error_type = None
    error_keywords = {
        "timeout": "timeout",
        "latency": "latency",
        "slow": "latency", 
        "crash": "crash",
        "down": "down",
        "error": "error",
        "fail": "failure",
        "connection": "connection",
        "pool": "connection_pool",
        "memory": "memory",
        "cpu": "cpu"
    }
    for kw, etype in error_keywords.items():
        if kw in lower_query:
            error_type = etype
            break
    
    # Environment
    environment = None
    if "prod" in lower_query:
        environment = "prod"
    elif "staging" in lower_query:
        environment = "staging"
    elif "dev" in lower_query:
        environment = "dev"
    
    return SlotInfo(
        service_name=service_name,
        error_type=error_type,
        environment=environment,
        additional_context=query
    )


def route_after_guard(state: GraphState) -> str:
    """Routing function after input guard"""
    intent = state.get("intent", "chat")
    
    if intent == "end":
        return "end"
    elif intent == "chat":
        return "chat_response"
    else:
        return "slot_check"
