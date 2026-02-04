from app.domain_init import get_active_domain
from app.llm_factory import get_llm
from app.state import DiagnosticResponse, GraphState, Message
from app.core.config import settings
from langchain_core.prompts import ChatPromptTemplate



def _get_chat_prompt(domain_config) -> ChatPromptTemplate:
    system_prompt = f"""<!-- 1. Task Context -->
{domain_config.chat_prompt.system_identity or "You are a helpful assistant."}

<!-- 2. Tone Context -->
Be warm, helpful, and approachable while maintaining professionalism.
Match the user's language ({domain_config.response_language} if they write in that language, otherwise follow their lead).
Keep responses concise but complete.

<!-- 4. Detailed Task Description & Rules -->
RULES:
1. For greetings: Respond warmly and briefly mention your capabilities
2. For capability questions: Explain what you can do clearly and offer to help
3. For unclear requests: Gently guide the user toward describing their issue related to {domain_config.display_name}
4. NEVER pretend to have capabilities you don't have
5. NEVER discuss topics unrelated to your role
6. If asked about sensitive topics, politely redirect to your core function
7. Do NOT use Pinyin or pronunciation guides in your response (e.g. no '(Qǐng wèn...)')

CAPABILITIES you can mention:
- {domain_config.display_name} specific tasks
- {", ".join(domain_config.intents)} related activities

<!-- 5. Examples -->
<examples>
  <example>
    <input>Hello</input>
    <output>Hello! I'm your {domain_config.display_name} assistant. How can I help you today?</output>
  </example>
  <example>
    <input>What can you do?</input>
    <output>I can help you with {domain_config.display_name} related questions, including {", ".join(domain_config.intents[:2])}. What would you like to know?</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Keep your response under 100 words unless detailed explanation is required.
Use natural, conversational language.
Do NOT use Pinyin in Chinese responses.
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
    
    # Get or preserve original query
    original_query = state.get("original_query") or state.get("query", "")

    return {
        **state,
        "response": clarification,
        # Mark that we're waiting for a clarification response
        "awaiting_clarification": True,
        "original_query": original_query,
    }


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
    
    goodbye_msg = f"Thank you for using {name}. The conversation has ended. Feel free to start a new conversation anytime!"

    if state.get("case_study_generated"):
        # Append goodbye to existing response (which contains the case study)
        current_response = state.get("response", "")
        return {
            **state,
            "response": f"{current_response}\n\n---\n\n{goodbye_msg}"
        }

    return {
        **state,
        "response": goodbye_msg,
    }
