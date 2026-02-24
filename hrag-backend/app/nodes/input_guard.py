import json
from typing import Literal, Optional

from app.core.config import settings
from app.core.logger import logger
from app.llm_factory import get_llm
from app.skill_registry import SkillRegistry, get_active_skill, list_available_skills, switch_skill
from app.state import DynamicSlotInfo, GraphState, SlotInfo
from langchain_core.prompts import ChatPromptTemplate


def _get_skill_routing_prompt(skills: list) -> ChatPromptTemplate:
    skill_descriptions = []
    for skill_name in skills:
        config = SkillRegistry.get_skill(skill_name)
        if config:
            keywords_sample = (
                config.routing_keywords[:10] if config.routing_keywords else []
            )
            keywords_str = ", ".join(str(k) for k in keywords_sample)
            skill_descriptions.append(
                f'<skill name="{skill_name}">\n'
                f"  Display: {config.display_name}\n"
                f"  Description: {config.description}\n"
                f"  Keywords: {keywords_str}\n"
                f"</skill>"
            )

    skills_xml = "\n".join(skill_descriptions)
    skill_names = ", ".join(skills)

    system_prompt = f"""<!-- 1. Task Context -->
You are SkillRouter. Your task is to classify which skill should handle the user's query.

<!-- 2. Tone Context -->
Be decisive and analytical. Match the query's core topic to the most relevant skill.
When the topic is ambiguous, prioritize the skill with more specific keywords.

<!-- 3. Background Data -->
<available_skills>
{skills_xml}
</available_skills>

<!-- 4. Detailed Task Description & Rules -->
RULES:
1. Output ONLY the skill name: {skill_names}
2. Choose the skill that best matches the user's query topic
3. If unsure, pick the most likely skill based on context
4. No explanation, just the skill name

<!-- 5. Examples -->
<examples>
  <example>
    <query>The api-gateway is returning 502 errors</query>
    <output>devops_incident</output>
  </example>
  <example>
    <query>Hello, how are you?</query>
    <output>hello</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output: A single skill name from [{skill_names}]. No punctuation, no explanation."""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "<query>{query}</query>"),
        ]
    )


async def _detect_skill_async(query: str) -> Optional[str]:
    available_skills = list_available_skills()

    if not available_skills:
        return None

    if len(available_skills) == 1:
        return available_skills[0]

    llm = get_llm()
    prompt = _get_skill_routing_prompt(available_skills)
    chain = prompt | llm

    try:
        result = await chain.ainvoke({"query": query})
        detected = result.content.strip().lower()

        for skill_name in available_skills:
            if skill_name.lower() in detected:
                return skill_name

        return available_skills[0]

    except Exception as e:
        logger.warning(f"Skill routing failed, defaulting to first skill: {e}")
        return available_skills[0]


def _get_classification_prompt(skill_config) -> ChatPromptTemplate:
    categories_xml = "<categories>\n"
    for intent in skill_config.intents:
        keywords = skill_config.intent_keywords.get(intent, [])
        keywords_str = (
            ", ".join([str(k) for k in keywords]) if keywords else "general query"
        )
        categories_xml += f'  <category name="{intent}">\n'
        categories_xml += f"    Keywords: {keywords_str}\n"
        categories_xml += "  </category>\n"
    categories_xml += "</categories>"

    system_prompt = f"""<!-- 1. Task Context -->
{skill_config.classification_prompt.system_identity or "You are IntentClassifier."}

<!-- 2. Tone Context -->
Be decisive and consistent. When the intent is ambiguous, lean toward the more specific action-oriented category.
Never classify greetings as actionable intents.

<!-- 3. Background Data -->
{categories_xml}

<!-- 4. Detailed Task Description & Rules -->
Classify the user's message into exactly ONE of the following categories.

STRICT RULES:
1. Output ONLY the category name: {", ".join(skill_config.intents)}
2. Do not include any explanation or additional text
3. Match intent based on keywords and context
4. Default to 'chat' for greetings, thanks, or off-topic queries

<!-- 5. Examples -->
<examples>
  <example>
    <input>Hi there!</input>
    <output>chat</output>
  </example>
  <example>
    <input>What is the status of my order?</input>
    <output>status</output>
  </example>
  <example>
    <input>Goodbye, thanks for your help</input>
    <output>end</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output format: Single word, lowercase, no punctuation.
Valid outputs: {" | ".join(skill_config.intents)}"""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "<input>{query}</input>"),
        ]
    )


def _get_slot_extraction_prompt(skill_config) -> ChatPromptTemplate:
    slots_xml = "<slot_schema>\n"

    for slot in skill_config.slots.required:
        examples = skill_config.slots.examples.get(slot, [])
        ex_str = f"Examples: {', '.join(examples)}" if examples else ""
        slots_xml += f'  <slot name="{slot}" type="string" required="true">\n'
        slots_xml += f"    Required field. {ex_str}\n"
        slots_xml += "  </slot>\n"

    for slot in skill_config.slots.optional:
        examples = skill_config.slots.examples.get(slot, [])
        ex_str = f"Examples: {', '.join(examples)}" if examples else ""
        slots_xml += f'  <slot name="{slot}" type="string" required="false">\n'
        slots_xml += f"    Optional field. {ex_str}\n"
        slots_xml += "  </slot>\n"

    slots_xml += "</slot_schema>"

    # Build schema display - need quadruple braces to escape through f-string AND LangChain
    # f-string: {{{{ -> {{ after first interpolation
    # LangChain: {{ -> { after second interpolation
    schema_fields = [
        f'"{s}": "string|null"'
        for s in skill_config.slots.required + skill_config.slots.optional
    ]
    schema_str = "{{{{" + ", ".join(schema_fields) + "}}}}"

    system_prompt = f"""<!-- 1. Task Context -->
You are SlotExtractor. Your responsibility is to extract structured information from user queries.

<!-- 2. Tone Context -->
Be precise and literal. Extract only values explicitly stated by the user.
Never infer or assume values that are not directly mentioned.

<!-- 3. Background Data -->
{slots_xml}

<!-- 4. Detailed Task Description & Rules -->
Extract the following fields from the user's query.

STRICT RULES:
1. Output ONLY valid JSON, no markdown code blocks
2. Use null for fields not explicitly mentioned
3. Extract exact values from the user input
4. Preserve the user's original wording when possible

<!-- 5. Examples -->
<examples>
  <example>
    <input>Show me orders from last week</input>
    <output>{{{{"order_id": null, "category": "orders", "timeframe": "last week"}}}}</output>
  </example>
  <example>
    <input>Delete item SKU-999</input>
    <output>{{{{"item_id": "SKU-999", "action": "delete", "timeframe": null}}}}</output>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output format: Raw JSON object only. No markdown.
Schema: {schema_str}"""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "<input>{query}</input>"),
            ("ai", "{{"),
        ]
    )


async def input_guard_node(state: GraphState) -> GraphState:
    query = state.get("query", "")

    clarification_response = state.get("clarification_response")
    if clarification_response:
        current_skill = get_active_skill()

        logger.debug(
            f"Processing clarification response: {clarification_response}"
        )

        if current_skill and state.get("slots"):
            llm = get_llm()
            extraction_prompt = _get_slot_extraction_prompt(current_skill)
            extraction_chain = extraction_prompt | llm

            existing_slots = state.get("slots")
            if isinstance(existing_slots, SlotInfo):
                existing_slots = existing_slots.to_dynamic()

            original_query = state.get("original_query", "")
            prev_clarification = state.get("clarification_question", "")

            enriched_query = f"""Original query: {original_query}
System asked: {prev_clarification}
User answered: {clarification_response}"""

            logger.debug(f"Enriched context for extraction: {enriched_query}")

            try:
                result = await extraction_chain.ainvoke({"query": enriched_query})
                content = result.content.strip()

                # Normalize smart quotes to standard quotes
                content = content.replace("\u201c", '"').replace("\u201d", '"')

                logger.debug(f"Raw extraction result: {repr(content)}")

                if not content.startswith("{"):
                    content = "{" + content

                if "```" in content:
                    parts = content.split("```")
                    for part in parts:
                        if part.strip().startswith("json"):
                            content = part.strip()[4:].strip()
                            break
                        elif part.strip().startswith("{"):
                            content = part.strip()
                            break

                brace_count = content.count("{") - content.count("}")
                if brace_count > 0:
                    content = content + "}" * brace_count

                logger.debug(f"Cleaned JSON: {content}")

                slot_data = json.loads(content)

                for key, value in slot_data.items():
                    if value is not None:
                        existing_slots.set_slot(key, value)
                        logger.debug(f"Set slot {key} = {value}")

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error during slot extraction: {e}")
                import re

                pattern = r'"(\w+)":\s*"([^"]+)"'
                matches = re.findall(pattern, content)
                for key, value in matches:
                    if value and value.lower() != "null":
                        existing_slots.set_slot(key, value)
                        logger.debug(f"Fallback set slot {key} = {value}")
            except Exception as e:
                logger.error(f"Clarification slot extraction error: {e}")

            logger.debug(f"Final slots: {existing_slots.get_filled_slots()}")

            return {
                **state,
                "slots": existing_slots,
                # Keep existing skill and intent
                "skill": state.get("skill"),
                "intent": state.get("intent"),
                "clarification_count": state.get("clarification_count", 0),
                "clarification_response": None,
            }

    detected_skill = await _detect_skill_async(query)
    if detected_skill:
        switch_skill(detected_skill)

    current_skill = get_active_skill()

    if not current_skill:
        logger.error("No active skill loaded!")
        return {**state, "intent": "end", "response": "System error: No skill loaded."}

    if not query.strip():
        return {**state, "intent": "chat", "response": "Please provide a message."}

    llm = get_llm()

    classification_prompt = _get_classification_prompt(current_skill)
    classification_chain = classification_prompt | llm

    try:
        result = await classification_chain.ainvoke({"query": query})
        intent_raw = result.content.strip().lower()
    except Exception as e:
        logger.warning(f"Intent classification failed, defaulting to chat: {e}")
        intent_raw = "chat"

    valid_intents = current_skill.intents
    matched_intent = next((i for i in valid_intents if i in intent_raw), "chat")

    needs_slots = matched_intent not in ["chat", "end"]

    slots = DynamicSlotInfo()
    slots.configure(
        required=current_skill.slots.required, optional=current_skill.slots.optional
    )

    if needs_slots:
        extraction_prompt = _get_slot_extraction_prompt(current_skill)
        extraction_chain = extraction_prompt | llm

        try:
            result = await extraction_chain.ainvoke({"query": query})
            content = result.content.strip()

            if not content.startswith("{"):
                content = "{" + content

            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    if part.strip().startswith("json"):
                        content = part.strip()[4:].strip()
                        break
                    elif part.strip().startswith("{"):
                        content = part.strip()
                        break

            # Balance braces
            brace_count = content.count("{") - content.count("}")
            if brace_count > 0:
                content = content + "}" * brace_count

            slot_data = json.loads(content)

            for key, value in slot_data.items():
                if value is not None:
                    slots.set_slot(key, value)

        except json.JSONDecodeError as e:
            logger.warning(f"Initial slot extraction JSON parse error: {e}")
            import re

            pattern = r'"(\w+)":\s*"([^"]+)"'
            matches = re.findall(pattern, content)
            for key, value in matches:
                if value and value.lower() != "null":
                    slots.set_slot(key, value)
        except Exception as e:
            logger.warning(f"Slot extraction failed: {e}")

    return {
        **state,
        "skill": current_skill.name,
        "intent": matched_intent,
        "slots": slots,
        "clarification_count": state.get("clarification_count", 0),
    }


def route_after_guard(state: GraphState) -> str:
    intent = state.get("intent", "chat")

    if intent == "end":
        return "end"
    elif intent == "chat":
        return "chat_response"
    else:
        return "slot_check"
