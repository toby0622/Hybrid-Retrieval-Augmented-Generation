"""
Response Generation Node
Formats the final response for the user
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.state import DiagnosticResponse, GraphState, Message
from config import settings


def get_llm():
    """Initialize LLM for chat responses."""
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.7,  # Higher temperature for more natural chat
    )


# =============================================================================
# CHAT_RESPONSE_PROMPT - Conversational Response Generation
# Anthropic 10-Element Framework Applied
# =============================================================================
CHAT_RESPONSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are DevOps Copilot, a friendly and professional AI assistant created by the Platform Engineering team.
Your primary mission is to help users investigate DevOps incidents, but you also engage in general conversation
when users want to chat, ask about your capabilities, or need guidance on how to use the system.

<!-- 2. Tone Context -->
Be warm, helpful, and approachable while maintaining professionalism.
Use a conversational but efficient tone - friendly without being overly casual.
Match the user's language (Traditional Chinese 繁體中文 if they write in Chinese, English otherwise).
Keep responses concise but complete (typically 2-4 sentences for greetings, more for explanations).

<!-- 4. Detailed Task Description & Rules -->
RULES:
1. For greetings: Respond warmly and briefly mention your capabilities
2. For capability questions: Explain what you can do clearly and offer to help
3. For unclear requests: Gently guide the user toward describing their DevOps issue
4. NEVER pretend to have capabilities you don't have
5. NEVER discuss topics unrelated to DevOps, technology, or your assistant role
6. If asked about sensitive topics, politely redirect to your core function

CAPABILITIES you can mention:
- Investigate production incidents and errors
- Analyze logs and error patterns
- Query knowledge base of past incidents
- Trace service dependencies and topology
- Provide root cause analysis and recommendations

<!-- 5. Examples -->
<examples>
  <example>
    <user_input>你好</user_input>
    <response>你好！我是 DevOps Copilot，專門協助調查生產環境事件與排除故障。您可以描述遇到的問題，例如服務錯誤、效能異常或系統告警，我會幫您診斷！</response>
  </example>
  <example>
    <user_input>What can you do?</user_input>
    <response>I'm your DevOps incident investigation assistant! I can help you:
• Diagnose production errors and service issues
• Analyze logs and trace error patterns
• Search our knowledge base for similar past incidents
• Provide root cause analysis with actionable recommendations

Just describe the issue you're seeing, and I'll help investigate!</response>
  </example>
  <example>
    <user_input>請問你是誰開發的？</user_input>
    <response>我是由 Platform Engineering 團隊開發的 DevOps Copilot。我的設計目標是幫助您快速診斷生產環境問題、分析事件根因，並提供解決建議。有什麼我可以幫您調查的嗎？</response>
  </example>
</examples>""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
<input>{query}</input>""",
        ),
    ]
)


async def chat_response_node(state: GraphState) -> GraphState:
    """
    Generate response for chat/greeting messages using LLM
    """
    query = state.get("query", "")

    try:
        llm = get_llm()
        chat_chain = CHAT_RESPONSE_PROMPT | llm
        result = await chat_chain.ainvoke({"query": query})
        response = result.content.strip()
    except Exception as e:
        # Fallback to static response if LLM fails
        lower_query = query.lower()
        if any(kw in lower_query for kw in ["hello", "hi", "hey", "你好", "哈囉"]):
            response = "你好！我是 DevOps Copilot，可以幫助你調查事件、分析日誌和查詢知識圖譜。請描述你遇到的問題，我會協助你診斷！"
        elif "help" in lower_query or "what" in lower_query or "幫" in lower_query:
            response = """我是 DevOps 事件回應助手，可以幫助你：

• **調查事件** - 描述你看到的錯誤或問題
• **分析日誌** - 貼上錯誤日誌或症狀
• **查詢知識庫** - 搜尋過去的事件和文件
• **找出根因** - 交叉比對拓撲與歷史資料

請描述你的問題，我會幫你診斷！"""
        else:
            response = "我在這裡幫助處理 DevOps 事件和故障排除。有什麼我可以幫忙的嗎？"

    return {**state, "response": response}


async def clarification_response_node(state: GraphState) -> GraphState:
    """
    Generate clarification question response
    """
    clarification = state.get("clarification_question", "")

    return {**state, "response": clarification}


async def diagnostic_response_node(state: GraphState) -> GraphState:
    """
    Format diagnostic response for presentation
    """
    diagnostic = state.get("diagnostic")
    reasoning_steps = state.get("reasoning_steps", [])

    if not diagnostic:
        return {
            **state,
            "response": "Unable to generate diagnostic analysis. Please provide more details.",
        }

    # Build formatted response
    response_parts = []

    # Add reasoning summary
    response_parts.append("## Analysis Complete\n")
    response_parts.append(f"根據混合檢索與日誌分析，發現潛在根因。\n")

    # Response will be enhanced by the diagnostic card in frontend
    response = "\n".join(response_parts)

    return {**state, "response": response}


async def end_conversation_node(state: GraphState) -> GraphState:
    """
    Handle conversation end
    """
    return {
        **state,
        "response": "Thank you for using DevOps Copilot. The conversation has ended. Feel free to start a new conversation anytime!",
    }
