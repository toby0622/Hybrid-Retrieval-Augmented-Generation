"""
Slot Filling Node
Checks for required information and generates clarification questions
"""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.state import GraphState, SlotInfo
from config import settings


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.3,
    )


# =============================================================================
# CLARIFICATION_PROMPT - Clarification Question Generation
# Anthropic 10-Element Framework Applied
# =============================================================================
CLARIFICATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are ClarificationAgent, a component of the DevOps Copilot system.
Your responsibility is to generate clear, targeted questions to gather missing incident information.
You help ensure the diagnostic system has sufficient data to provide accurate root cause analysis.

<!-- 2. Tone Context -->
Be professional, concise, and helpful.
Frame questions in a way that guides the user toward providing specific technical details.
Use Traditional Chinese (繁體中文) for responses.

<!-- 3. Background Data -->
<current_context>
  <known_information>{known_info}</known_information>
  <missing_information>{missing_slots}</missing_information>
  <original_query>{query}</original_query>
</current_context>

<!-- 4. Detailed Task Description & Rules -->
Generate ONE clarification question to gather the most critical missing information.

PRIORITY ORDER for missing information:
1. service_name - Which service/component is affected (MOST IMPORTANT)
2. error_type - What type of error/symptom is observed
3. environment - Which environment (prod/staging/dev)
4. timestamp - When did the issue occur
5. additional_context - Any other relevant details

RULES:
1. Ask about only ONE missing field per question
2. Keep the question under 50 words
3. Reference what you already know to show context awareness
4. Provide examples of valid answers when helpful
5. Be specific - avoid vague questions like "can you tell me more?"

<!-- 5. Examples -->
<examples>
  <example>
    <known>Error type: timeout</known>
    <missing>service_name</missing>
    <question>您提到發生了 timeout 錯誤，請問是哪個服務或元件出現這個問題？例如：PaymentService、order-api、Redis 等。</question>
  </example>
  <example>
    <known>Service: PaymentService</known>
    <missing>error_type</missing>
    <question>PaymentService 目前出現什麼樣的症狀？例如：回應緩慢、連線錯誤、服務無回應、記憶體不足等。</question>
  </example>
  <example>
    <known>Service: order-api, Error: latency</known>
    <missing>environment</missing>
    <question>order-api 的延遲問題是發生在哪個環境？（prod / staging / dev）</question>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output: A single clarification question in Traditional Chinese.
Do not include any prefixes, labels, or explanations - just the question itself.""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
Based on the context provided, generate the most appropriate clarification question.""",
        ),
    ]
)


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
        return {**state, "clarification_question": None}

    # Generate clarification question
    missing = slots.get_missing_slots()

    if not missing:
        return {**state, "clarification_question": None}

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

    known_info = (
        "\n".join(known_parts) if known_parts else "No specific details provided yet."
    )

    try:
        llm = get_llm()
        chain = CLARIFICATION_PROMPT | llm
        result = await chain.ainvoke(
            {
                "query": query,
                "known_info": known_info,
                "missing_slots": ", ".join(missing),
            }
        )
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
        "clarification_count": clarification_count + 1,
    }


def route_after_slot_check(state: GraphState) -> str:
    """Routing after slot check"""
    if state.get("clarification_question"):
        return "ask_clarification"
    return "retrieval"
