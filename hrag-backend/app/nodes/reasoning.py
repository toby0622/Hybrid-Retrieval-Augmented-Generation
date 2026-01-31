"""
LLM Reasoning Node
Context aggregation, tool use simulation, and diagnostic path generation
"""

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
        temperature=0.2,
    )


# =============================================================================
# Dynamic Prompt Generation
# =============================================================================


def _get_reasoning_prompt(domain_config) -> ChatPromptTemplate:
    """Generate reasoning prompt based on domain config."""
    
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
        ("ai", "<analysis>\n  <thinking>"),  # Prefill
    ])


async def mcp_tool_node(state: GraphState) -> GraphState:
    """
    MCP Tool Use Node
    Currently skipped until MCP integration is implemented.
    """
    # TODO: Implement actual MCP protocol connection
    return {**state, "mcp_results": []}


async def reasoning_node(state: GraphState) -> GraphState:
    """
    LLM Reasoning Node

    Aggregates context from all sources and generates diagnostic analysis.
    """
    query = state.get("query", "")
    slots = state.get("slots")
    
    # Handle legacy slots
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

    # Build context strings
    slots_info = slots.to_display_string()

    graph_context = _format_results(graph_results) or "No graph results available."
    vector_context = _format_results(vector_results) or "No document matches found."
    mcp_context = _format_results(mcp_results) or "No real-time data available."

    # Track reasoning steps
    reasoning_steps = [
        f"Input Guardrails: Intent '{state.get('intent', 'unknown')}' detected",
        f"Slot Extraction: {len(slots.get_filled_slots())} slots identified",
        f"Graph Search: {len(graph_results)} results",
        f"Vector Search: {len(vector_results)} matches",
        "LLM Reasoning: Synthesizing analysis",
    ]

    # Generate LLM analysis
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
        # Prepend the prefill to complete the XML structure
        llm_analysis = "<analysis>\n  <thinking>" + result.content
    except Exception as e:
        print(f"[Reasoning] LLM error: {e}")
        llm_analysis = f"Analysis error: {e}"

    # Build diagnostic path dynamically from LLM output
    diagnostic = _parse_diagnostic_response(llm_analysis, query)

    return {
        **state,
        "reasoning_steps": reasoning_steps,
        "diagnostic": diagnostic,
        "aggregated_context": f"{graph_context}\n\n{vector_context}\n\n{mcp_context}",
    }


def _format_results(results: List[RetrievalResult]) -> str:
    """Format retrieval results into readable text"""
    if not results:
        return ""

    parts = []
    for r in results:
        parts.append(f"**{r.title}** (confidence: {r.confidence:.2f})\n{r.content}")
    return "\n\n".join(parts)


def _parse_diagnostic_response(llm_output: str, query: str) -> DiagnosticResponse:
    """
    Parse the XML output from the LLM into a structured DiagnosticResponse.
    Robustly handles malformed XML using regex.
    """
    steps = []
    
    # Extract root cause / conclusion
    root_cause_match = re.search(r"<root_cause[^>]*>(.*?)</root_cause>", llm_output, re.DOTALL)
    root_cause = root_cause_match.group(1).strip() if root_cause_match else "Analysis incomplete"
    
    # Extract evidence
    evidence_match = re.search(r"<evidence>(.*?)</evidence>", llm_output, re.DOTALL)
    evidence = evidence_match.group(1).strip() if evidence_match else ""
    
    # Extract recommendations
    recommendations = re.findall(r"<action[^>]*>(.*?)</action>", llm_output, re.DOTALL)
    suggestion = recommendations[0].strip() if recommendations else "No specific recommendation."
    
    # Create diagnostic steps based on findings
    steps.append(DiagnosticStep(
        id="result",
        source="LLM Analysis",
        title="Conclusion",
        detail=root_cause,
        status="info",
        is_root=True,
    ))
    
    if evidence:
        steps.append(DiagnosticStep(
            id="evidence",
            source="Evidence",
            title="Supporting Data",
            detail=evidence[:100] + "..." if len(evidence) > 100 else evidence,
            status="info",
        ))

    return DiagnosticResponse(
        path=steps,
        suggestion=suggestion,
        confidence=0.85
    )
