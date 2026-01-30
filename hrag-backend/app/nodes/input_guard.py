"""
Input Guard Node
Routes user input: chat / incident query / end conversation
"""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.state import GraphState, SlotInfo
from config import settings


# Initialize LLM (LM Studio compatible via OpenAI API)
def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.1,
    )


# =============================================================================
# CLASSIFICATION_PROMPT - Intent Classification
# Anthropic 10-Element Framework Applied
# =============================================================================
CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are IntentClassifier, an AI component within the DevOps Copilot system.
Your sole responsibility is to classify user messages into one of three intent categories.
You were created by the DevOps Platform Team to route user queries to the appropriate processing pipeline.

<!-- 2. Tone Context -->
Be precise and analytical. Do not add any conversational elements.
Your output is consumed by downstream systems, not humans directly.

<!-- 4. Detailed Task Description & Rules -->
Classify the user's message into exactly ONE of the following categories:

<categories>
  <category name="incident">
    User is reporting an issue, asking about errors, troubleshooting, or investigating a problem.
    Keywords: error, slow, down, fail, issue, problem, timeout, crash, latency, 500, 503, OOM
  </category>
  <category name="chat">
    General greetings, help requests, capability questions, or unrelated conversation.
    Keywords: hello, hi, help, what can you do, who are you, 你好, 哈囉
  </category>
  <category name="end">
    User wants to end the conversation or indicates completion.
    Keywords: bye, goodbye, thanks, done, that's all, 謝謝, 結束
  </category>
</categories>

STRICT RULES:
1. Output ONLY the category name: incident, chat, or end
2. Do not include any explanation or additional text
3. When uncertain between categories, prefer "incident" if any technical terms are present
4. Prefer "chat" only for clear greetings or meta-questions about the assistant

<!-- 5. Examples -->
<examples>
  <example>
    <user_input>PaymentService 回應很慢</user_input>
    <output>incident</output>
  </example>
  <example>
    <user_input>你好，請問你是誰？</user_input>
    <output>chat</output>
  </example>
  <example>
    <user_input>Error 500 in production API gateway</user_input>
    <output>incident</output>
  </example>
  <example>
    <user_input>謝謝你的幫助，沒問題了</user_input>
    <output>end</output>
  </example>
  <example>
    <user_input>What can you help me with?</user_input>
    <output>chat</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output format: Single word, lowercase, no punctuation.
Valid outputs: incident | chat | end""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
<input>{query}</input>""",
        ),
    ]
)


# =============================================================================
# SLOT_EXTRACTION_PROMPT - Incident Information Extraction
# Anthropic 10-Element Framework Applied
# =============================================================================
SLOT_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are SlotExtractor, an AI component within the DevOps Copilot system.
Your responsibility is to extract structured incident information from user queries.
You were created to enable downstream diagnostic pipelines to process incidents efficiently.

<!-- 2. Tone Context -->
Be precise and factual. Extract only explicitly stated information.
Never infer, guess, or hallucinate data that is not clearly mentioned.

<!-- 4. Detailed Task Description & Rules -->
Extract the following fields from the user's incident report:

<slot_schema>
  <slot name="service_name" type="string|null">
    The name of the affected service, component, or microservice.
    Examples: PaymentService, order-api, Redis, Kafka, MySQL
  </slot>
  <slot name="error_type" type="string|null">
    The type of error or symptom observed.
    Valid values: timeout, latency, crash, down, error, connection, memory, cpu, disk, oom
  </slot>
  <slot name="timestamp" type="string|null">
    When the issue occurred. Accept any format mentioned by user.
  </slot>
  <slot name="environment" type="string|null">
    The deployment environment.
    Valid values: prod, production, staging, dev, development, test
  </slot>
  <slot name="cluster" type="string|null">
    The cluster or region name if mentioned.
  </slot>
  <slot name="additional_context" type="string|null">
    Any other relevant details not captured above.
  </slot>
</slot_schema>

STRICT RULES:
1. Output ONLY valid JSON, no markdown code blocks
2. Use null for fields not explicitly mentioned
3. Do not infer service names from context
4. Normalize environment names (e.g., "production" -> "prod")
5. Keep additional_context concise (max 100 characters)

<!-- 5. Examples -->
<examples>
  <example>
    <user_input>PaymentService 在 prod 環境出現 timeout 錯誤</user_input>
    <output>{{"service_name": "PaymentService", "error_type": "timeout", "timestamp": null, "environment": "prod", "cluster": null, "additional_context": null}}</output>
  </example>
  <example>
    <user_input>昨天下午三點 order-api 連線池爆滿</user_input>
    <output>{{"service_name": "order-api", "error_type": "connection", "timestamp": "昨天下午三點", "environment": null, "cluster": null, "additional_context": "連線池爆滿"}}</output>
  </example>
  <example>
    <user_input>系統很慢</user_input>
    <output>{{"service_name": null, "error_type": "latency", "timestamp": null, "environment": null, "cluster": null, "additional_context": null}}</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output format: Raw JSON object only. No markdown, no explanation.
Schema: {{"service_name": str|null, "error_type": str|null, "timestamp": str|null, "environment": str|null, "cluster": str|null, "additional_context": str|null}}""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
<input>{query}</input>""",
        ),
        ("ai", "{{"),  # <!-- 10. Prefilled Response -->
    ]
)


async def input_guard_node(state: GraphState) -> GraphState:
    """
    Input Guardrails Node

    1. Classifies user intent (chat/incident/end)
    2. For incident queries, extracts initial slots
    """
    query = state.get("query", "")

    if not query.strip():
        return {**state, "intent": "chat", "response": "Please provide a message."}

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
        if any(
            kw in lower_query
            for kw in [
                "error",
                "slow",
                "down",
                "fail",
                "issue",
                "problem",
                "timeout",
                "crash",
            ]
        ):
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
            # Handle prefill: response starts after the prefilled "{"
            # So we need to prepend "{" to complete the JSON
            if not content.startswith("{"):
                content = "{" + content
            # Handle markdown code blocks (fallback)
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
        "clarification_count": state.get("clarification_count", 0),
    }


def _extract_slots_fallback(query: str) -> SlotInfo:
    """Fallback slot extraction when LLM is unavailable."""
    import re

    lower_query = query.lower()

    # Known service names (add more as needed)
    known_services = [
        "PaymentService",
        "OrderService",
        "UserService",
        "NotificationService",
        "InventoryService",
        "payment-service",
        "order-service",
        "user-service",
        "payment",
        "order",
        "user",
        "inventory",
        "notification",
        "api",
        "gateway",
        "auth",
        "database",
        "redis",
        "kafka",
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
        "cpu": "cpu",
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
        additional_context=query,
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
