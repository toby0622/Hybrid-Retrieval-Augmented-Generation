import json
from typing import Literal, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.domain_config import DomainRegistry
from app.domain_init import get_active_domain, switch_domain, list_available_domains
from app.state import DynamicSlotInfo, GraphState, SlotInfo
from config import settings


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.1,
    )


def _get_domain_routing_prompt(domains: list) -> ChatPromptTemplate:
    domain_descriptions = []
    for domain_name in domains:
        config = DomainRegistry.get_domain(domain_name)
        if config:
            keywords_sample = config.routing_keywords[:10] if config.routing_keywords else []
            keywords_str = ", ".join(str(k) for k in keywords_sample)
            domain_descriptions.append(
                f'<domain name="{domain_name}">\n'
                f'  Display: {config.display_name}\n'
                f'  Description: {config.description}\n'
                f'  Keywords: {keywords_str}\n'
                f'</domain>'
            )
    
    domains_xml = "\n".join(domain_descriptions)
    domain_names = ", ".join(domains)
    
    system_prompt = f"""You are DomainRouter. Your task is to classify which domain should handle the user's query.

<available_domains>
{domains_xml}
</available_domains>

RULES:
1. Output ONLY the domain name: {domain_names}
2. Choose the domain that best matches the user's query topic
3. If unsure, pick the most likely domain based on context
4. No explanation, just the domain name"""

    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "<query>{query}</query>"),
    ])


async def _detect_domain_async(query: str) -> Optional[str]:
    available_domains = list_available_domains()
    
    if not available_domains:
        return None
    
    if len(available_domains) == 1:
        return available_domains[0]
    
    llm = get_llm()
    prompt = _get_domain_routing_prompt(available_domains)
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({"query": query})
        detected = result.content.strip().lower()
        
        for domain_name in available_domains:
            if domain_name.lower() in detected:
                return domain_name
        
        return available_domains[0]
        
    except Exception as e:
        return available_domains[0]


def _get_classification_prompt(domain_config) -> ChatPromptTemplate:
    categories_xml = "<categories>\n"
    for intent in domain_config.intents:
        keywords = domain_config.intent_keywords.get(intent, [])
        keywords_str = ", ".join([str(k) for k in keywords]) if keywords else "general query"
        categories_xml += f'  <category name="{intent}">\n'
        categories_xml += f"    Keywords: {keywords_str}\n"
        categories_xml += "  </category>\n"
    categories_xml += "</categories>"

    system_prompt = f"""<!-- 1. Task Context -->
{domain_config.classification_prompt.system_identity or "You are IntentClassifier."}

<!-- 4. Detailed Task Description & Rules -->
Classify the user's message into exactly ONE of the following categories:

{categories_xml}

STRICT RULES:
1. Output ONLY the category name: {", ".join(domain_config.intents)}
2. Do not include any explanation or additional text
3. Match intent based on keywords and context

<!-- 9. Output Formatting -->
Output format: Single word, lowercase, no punctuation.
Valid outputs: {" | ".join(domain_config.intents)}"""

    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "<input>{query}</input>"),
    ])


def _get_slot_extraction_prompt(domain_config) -> ChatPromptTemplate:
    slots_xml = "<slot_schema>\n"
    
    for slot in domain_config.slots.required:
        examples = domain_config.slots.examples.get(slot, [])
        ex_str = f"Examples: {', '.join(examples)}" if examples else ""
        slots_xml += f'  <slot name="{slot}" type="string" required="true">\n'
        slots_xml += f"    Required field. {ex_str}\n"
        slots_xml += "  </slot>\n"
        
    for slot in domain_config.slots.optional:
        examples = domain_config.slots.examples.get(slot, [])
        ex_str = f"Examples: {', '.join(examples)}" if examples else ""
        slots_xml += f'  <slot name="{slot}" type="string" required="false">\n'
        slots_xml += f"    Optional field. {ex_str}\n"
        slots_xml += "  </slot>\n"
        
    slots_xml += "</slot_schema>"
    
    schema_fields = [f'"{s}": "string|null"' for s in domain_config.slots.required + domain_config.slots.optional]
    schema_str = "{{" + ", ".join(schema_fields) + "}}"

    system_prompt = f"""<!-- 1. Task Context -->
You are SlotExtractor. Your responsibility is to extract structured information from user queries.

<!-- 4. Detailed Task Description & Rules -->
Extract the following fields from the user's query:

{slots_xml}

STRICT RULES:
1. Output ONLY valid JSON, no markdown code blocks
2. Use null for fields not explicitly mentioned
3. Extract exact values from the user input

<!-- 9. Output Formatting -->
Output format: Raw JSON object only. No markdown.
Schema: {schema_str}"""

    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "<input>{query}</input>"),
        ("ai", "{{"),
    ])


async def input_guard_node(state: GraphState) -> GraphState:
    query = state.get("query", "")
    
    detected_domain = await _detect_domain_async(query)
    if detected_domain:
        switch_domain(detected_domain)
    
    current_domain = get_active_domain()
    
    if not current_domain:
        print("[Error] No active domain loaded!")
        return {**state, "intent": "end", "response": "System error: No domain loaded."}

    if not query.strip():
        return {**state, "intent": "chat", "response": "Please provide a message."}

    llm = get_llm()

    classification_prompt = _get_classification_prompt(current_domain)
    classification_chain = classification_prompt | llm
    
    try:
        result = await classification_chain.ainvoke({"query": query})
        intent_raw = result.content.strip().lower()
    except Exception as e:
        intent_raw = "chat"

    valid_intents = current_domain.intents
    matched_intent = next((i for i in valid_intents if i in intent_raw), "chat")
    
    needs_slots = matched_intent not in ["chat", "end"]
    
    slots = DynamicSlotInfo()
    slots.configure(
        required=current_domain.slots.required,
        optional=current_domain.slots.optional
    )

    if needs_slots:
        extraction_prompt = _get_slot_extraction_prompt(current_domain)
        extraction_chain = extraction_prompt | llm
        
        try:
            result = await extraction_chain.ainvoke({"query": query})
            content = result.content.strip()
            
            if not content.startswith("{"):
                content = "{" + content
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            slot_data = json.loads(content)
            
            for key, value in slot_data.items():
                if value is not None:
                    slots.set_slot(key, value)
                    
        except Exception as e:
            pass

    return {
        **state,
        "domain": current_domain.name,
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
