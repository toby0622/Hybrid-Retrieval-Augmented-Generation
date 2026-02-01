from app.domain_init import get_active_domain
from app.state import DynamicSlotInfo, GraphState, SlotInfo
from config import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.3,
    )


def _get_clarification_prompt(domain_config) -> ChatPromptTemplate:
    examples_xml = "<examples>\n"
    if domain_config.clarification_prompt.examples:
        for ex in domain_config.clarification_prompt.examples:
            if isinstance(ex, dict):
                known = ex.get("known", "")
                missing = ex.get("missing", "")
                question = ex.get("question", "")
                examples_xml += "  <example>\n"
                examples_xml += f"    <known>{known}</known>\n"
                examples_xml += f"    <missing>{missing}</missing>\n"
                examples_xml += f"    <question>{question}</question>\n"
                examples_xml += "  </example>\n"
    elif domain_config.slots.required:
        examples_xml += "  <example>\n"
        examples_xml += "    <known>Partial info provided</known>\n"
        examples_xml += f"    <missing>{domain_config.slots.required[0]}</missing>\n"
        examples_xml += f"    <question>Could you provide the {domain_config.slots.required[0]}?</question>\n"
        examples_xml += "  </example>\n"
    examples_xml += "</examples>"

    priority_list = ""
    for i, slot in enumerate(domain_config.slots.required, 1):
        priority_list += f"{i}. {slot} (REQUIRED)\n"
    for i, slot in enumerate(
        domain_config.slots.optional, len(domain_config.slots.required) + 1
    ):
        priority_list += f"{i}. {slot} (OPTIONAL)\n"

    system_prompt = f"""<!-- 1. Task Context -->
{domain_config.clarification_prompt.system_identity or "You are ClarificationAgent."}
Your responsibility is to generate clear, targeted questions to gather missing information.

<!-- 2. Tone Context -->
Be professional, concise, and helpful. Guide the user toward providing specific details.
Use {domain_config.response_language} for responses.

<!-- 3. Background Data -->
<current_context>
  <known_information>{{known_info}}</known_information>
  <missing_information>{{missing_slots}}</missing_information>
  <original_query>{{query}}</original_query>
</current_context>

<!-- 4. Detailed Task Description & Rules -->
Generate ONE clarification question to gather the most critical missing information.

PRIORITY ORDER:
{priority_list}

RULES:
1. Ask about only ONE missing field per question
2. Keep the question under 50 words
3. Reference what you already know to show context awareness
4. Provide examples of valid answers when helpful

<!-- 5. Examples -->
{examples_xml}

<!-- 9. Output Formatting -->
Output: A single clarification question in {domain_config.response_language}.
Do not include any prefixes, labels, or explanations - just the question itself."""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Based on the context provided, generate the most appropriate clarification question.",
            ),
        ]
    )


MAX_CLARIFICATION_ROUNDS = 3


async def slot_check_node(state: GraphState) -> GraphState:
    slots = state.get("slots")
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()

    query = state.get("query", "")
    clarification_count = state.get("clarification_count", 0)

    current_domain = get_active_domain()
    if not current_domain:
        return {**state, "clarification_question": None}

    slots.configure(
        required=current_domain.slots.required, optional=current_domain.slots.optional
    )

    if slots.is_sufficient() or clarification_count >= MAX_CLARIFICATION_ROUNDS:
        return {**state, "clarification_question": None}

    missing = slots.get_missing_slots()

    if not missing:
        return {**state, "clarification_question": None}

    filled = slots.get_filled_slots()
    known_info = "\n".join([f"{k}: {v}" for k, v in filled.items()])
    if not known_info:
        known_info = "No specific details provided yet."

    llm = get_llm()
    prompt = _get_clarification_prompt(current_domain)
    chain = prompt | llm

    try:
        result = await chain.ainvoke(
            {
                "query": query,
                "known_info": known_info,
                "missing_slots": ", ".join(missing),
            }
        )
        clarification = result.content.strip()
    except Exception as e:
        print(f"[SlotFilling] generation error: {e}")
        clarification = f"Could you please provide more details regarding {missing[0]}?"

    return {
        **state,
        "clarification_question": clarification,
        "clarification_count": clarification_count + 1,
    }


def route_after_slot_check(state: GraphState) -> str:
    if state.get("clarification_question"):
        return "ask_clarification"
    return "retrieval"
