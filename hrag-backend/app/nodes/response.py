from app.domain_init import get_active_domain
from app.state import DiagnosticResponse, GraphState, Message
from config import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.7,
    )


def _get_chat_prompt(domain_config) -> ChatPromptTemplate:
    system_prompt = f"""<!-- 1. Task Context -->
{domain_config.chat_turn_prompt.system_identity or "You are a helpful assistant."}

<!-- 2. Tone Context -->
Be warm, helpful, and approachable while maintaining professionalism.
Match the user's language ({domain_config.response_language} if they write in that language, otherwise generic).
Keep responses concise but complete.

<!-- 4. Detailed Task Description & Rules -->
RULES:
1. For greetings: Respond warmly and briefly mention your capabilities
2. For capability questions: Explain what you can do clearly and offer to help
3. For unclear requests: Gently guide the user toward describling their issue related to {domain_config.display_name}
4. NEVER pretend to have capabilities you don't have
5. NEVER discuss topics unrelated to your role
6. If asked about sensitive topics, politely redirect to your core function

CAPABILITIES you can mention:
- {domain_config.display_name} specific tasks
- {", ".join(domain_config.intents)} related activities
"""
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "<input>{query}</input>"),
        ]
    )


async def chat_response_node(state: GraphState) -> GraphState:
    query = state.get("query", "")
    current_domain = get_active_domain()

    if not current_domain:
        return {**state, "response": "System error: Domain not initialized."}

    llm = get_llm()
    chat_prompt = _get_chat_prompt(current_domain)
    chat_chain = chat_prompt | llm

    try:
        result = await chat_chain.ainvoke({"query": query})
        response = result.content.strip()
    except Exception as e:
        print(f"[ChatResponse] generation error: {e}")
        response = (
            "I'm having trouble generating a response right now. Please try again."
        )

    return {**state, "response": response}


async def clarification_response_node(state: GraphState) -> GraphState:
    clarification = state.get("clarification_question", "")

    return {**state, "response": clarification}


async def diagnostic_response_node(state: GraphState) -> GraphState:
    diagnostic = state.get("diagnostic")

    current_domain = get_active_domain()
    lang = current_domain.response_language if current_domain else "English"

    if not diagnostic:
        return {
            **state,
            "response": "Unable to generate analysis. Please provide more details.",
        }

    response_parts = []

    response_parts.append("## Analysis Complete\n")
    if "Chinese" in lang or "中文" in lang:
        response_parts.append(f"根據混合檢索與分析，發現以下結果。\n")
    else:
        response_parts.append(
            f"Based on hybrid retrieval and analysis, here are the findings.\n"
        )

    response = "\n".join(response_parts)

    return {**state, "response": response}


async def end_conversation_node(state: GraphState) -> GraphState:
    current_domain = get_active_domain()
    name = current_domain.display_name if current_domain else "the system"

    return {
        **state,
        "response": f"Thank you for using {name}. The conversation has ended. Feel free to start a new conversation anytime!",
    }
