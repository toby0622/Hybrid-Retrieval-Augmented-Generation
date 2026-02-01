import re
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.domain_init import get_active_domain
from app.state import (DiagnosticResponse, DiagnosticStep, DynamicSlotInfo,
                       GraphState, RetrievalResult, SlotInfo)
from config import settings


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.5,
    )


def _get_reasoning_prompt(domain_config) -> ChatPromptTemplate:
    system_prompt = f"""<!-- 1. Task Context -->
{domain_config.reasoning_prompt.system_identity or "You are the Core Reasoning Engine."}
Your responsibility is to synthesize information from multiple sources and provide accurate analysis.

<!-- 2. Tone Context -->
Be analytical, precise, and solution-oriented.
Respond in {domain_config.response_language}.

<!-- 3. Background Data -->
<incident_context>
  <user_query>{{query}}</user_query>
  <extracted_slots>{{slots_info}}</extracted_slots>
</incident_context>

<evidence_sources>
  <graph_topology_results>
    {{graph_context}}
  </graph_topology_results>
  
  <vector_search_results>
    {{vector_context}}
  </vector_search_results>
  
  <realtime_metrics>
    {{mcp_context}}
  </realtime_metrics>
</evidence_sources>

<!-- 4. Detailed Task Description & Rules -->
Perform comprehensive analysis following this methodology:

1. Identification - What is the core issue/topic?
2. Correlation - What do the data sources tell us?
3. Conclusion - What is the answer or root cause?
4. Recommendation - What should be done next?

RULES:
1. Base all conclusions on provided evidence
2. Clearly distinguish between confirmed facts and inferences
3. Provide confidence levels (High/Medium/Low)
4. Reference specific evidence when making claims

<!-- 8. Thinking Step by Step -->
Before providing your final analysis, think through the problem systematically.
Use the <thinking> tags to show your reasoning process.

<!-- 9. Output Formatting -->
Structure your response as follows:

<analysis>
  <thinking>
    [Your step-by-step reasoning]
  </thinking>
  
  <diagnosis>
    <root_cause confidence="High|Medium|Low">
      [Main conclusion or root cause]
    </root_cause>
    <evidence>
      [Supporting evidence from data]
    </evidence>
    <impact>
      [Impact or scope of the findings]
    </impact>
  </diagnosis>
  
  <recommendations>
    <action priority="1">
      [Primary recommendation]
    </action>
    <action priority="2">
      [Secondary recommendation]
    </action>
  </recommendations>
</analysis>"""

    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Analyze the context and provide your assessment."),
        ("ai", "<analysis>\n  <thinking>"),
    ])


async def mcp_tool_node(state: GraphState) -> GraphState:
    return {**state, "mcp_results": []}


async def reasoning_node(state: GraphState) -> GraphState:
    query = state.get("query", "")
    slots = state.get("slots")
    
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()

    graph_results = state.get("graph_results", [])
    vector_results = state.get("vector_results", [])
    mcp_results = state.get("mcp_results", [])
    
    current_domain = get_active_domain()
    if not current_domain:
        return {**state, "response": "System error: Domain not initialized."}

    slots_info = slots.to_display_string()

    graph_context = _format_results(graph_results) or "No graph results available."
    vector_context = _format_results(vector_results) or "No document matches found."
    mcp_context = _format_results(mcp_results) or "No real-time data available."

    reasoning_steps = [
        f"Input Guardrails: Intent '{state.get('intent', 'unknown')}' detected",
        f"Slot Extraction: {len(slots.get_filled_slots())} slots identified",
        f"Graph Search: {len(graph_results)} results",
        f"Vector Search: {len(vector_results)} matches",
        "LLM Reasoning: Synthesizing analysis",
    ]

    llm_analysis = "Analysis failed."
    try:
        llm = get_llm()
        prompt = _get_reasoning_prompt(current_domain)
        chain = prompt | llm
        result = await chain.ainvoke(
            {
                "query": query,
                "slots_info": slots_info,
                "graph_context": graph_context,
                "vector_context": vector_context,
                "mcp_context": mcp_context,
            }
        )
        llm_analysis = "<analysis>\n  <thinking>" + result.content
    except Exception as e:
        llm_analysis = f"Analysis error: {e}"

    diagnostic = _parse_diagnostic_response(
        llm_analysis, 
        query, 
        graph_results=graph_results,
        vector_results=vector_results
    )

    return {
        **state,
        "reasoning_steps": reasoning_steps,
        "diagnostic": diagnostic,
        "aggregated_context": f"{graph_context}\n\n{vector_context}\n\n{mcp_context}",
    }


def _format_results(results: List[dict]) -> str:
    if not results:
        return ""

    parts = []
    for r in results:
        title = r.get("title", "Unknown")
        confidence = r.get("confidence", 0.0)
        content = r.get("content", "")
        parts.append(f"**{title}** (confidence: {confidence:.2f})\n{content}")
    return "\n\n".join(parts)


def _parse_diagnostic_response(
    llm_output: str, 
    query: str,
    graph_results: List[dict] = None,
    vector_results: List[dict] = None
) -> DiagnosticResponse:
    steps = []
    graph_results = graph_results or []
    vector_results = vector_results or []
    
    if graph_results:
        graph_summary_parts = []
        for r in graph_results[:5]:
            title = r.get("title", "Graph Result")
            content = r.get("content", "")
            summary = f"• {title}: {content[:80]}..." if len(content) > 80 else f"• {title}: {content}"
            graph_summary_parts.append(summary)
            
        graph_summary = "\n".join(graph_summary_parts)
        
        steps.append(DiagnosticStep(
            id="graph",
            source="Graph Search",
            title=f"Knowledge Graph ({len(graph_results)} results)",
            detail=graph_summary,
            status="info",
            is_parallel=True,
            raw_content={"type": "graph", "data": [{"title": r.get("title"), "content": r.get("content")} for r in graph_results]},
        ))
    else:
        steps.append(DiagnosticStep(
            id="graph",
            source="Graph Search",
            title="Knowledge Graph (0 results)",
            detail="No graph results found for this query.",
            status="warning",
            is_parallel=True,
        ))
    
    if vector_results:
        vector_summary_parts = []
        for r in vector_results[:5]:
            title = r.get("title", "Document")
            confidence = r.get("confidence", 0.0)
            vector_summary_parts.append(f"• {title} (score: {confidence:.2f})")
            
        vector_summary = "\n".join(vector_summary_parts)
        
        steps.append(DiagnosticStep(
            id="vector",
            source="Vector Search",
            title=f"Semantic Search ({len(vector_results)} matches)",
            detail=vector_summary,
            status="info",
            is_parallel=True,
            raw_content={"type": "log", "data": [{"title": r.get("title"), "content": r.get("content"), "score": r.get("confidence")} for r in vector_results]},
        ))
    else:
        steps.append(DiagnosticStep(
            id="vector",
            source="Vector Search",
            title="Semantic Search (0 matches)",
            detail="No relevant documents found.",
            status="warning",
            is_parallel=True,
        ))
    
    root_cause_match = re.search(r"<root_cause[^>]*>(.*?)</root_cause>", llm_output, re.DOTALL)
    root_cause = root_cause_match.group(1).strip() if root_cause_match else "Analysis incomplete"
    
    evidence_match = re.search(r"<evidence>(.*?)</evidence>", llm_output, re.DOTALL)
    evidence = evidence_match.group(1).strip() if evidence_match else ""
    
    recommendations = re.findall(r"<action[^>]*>(.*?)</action>", llm_output, re.DOTALL)
    suggestion = recommendations[0].strip() if recommendations else "No specific recommendation."
    
    steps.append(DiagnosticStep(
        id="result",
        source="LLM Analysis",
        title="Conclusion",
        detail=root_cause,
        status="info",
        is_root=True,
        raw_content={"type": "markdown", "data": evidence} if evidence else None,
    ))

    return DiagnosticResponse(
        path=steps,
        suggestion=suggestion,
        confidence=0.85
    )
