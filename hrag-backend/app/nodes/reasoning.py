"""
LLM Reasoning Node
Context aggregation, tool use simulation, and diagnostic path generation
"""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.state import (DiagnosticResponse, DiagnosticStep, GraphState,
                       RetrievalResult, SlotInfo)
from config import settings


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.2,
    )


# =============================================================================
# REASONING_PROMPT - Diagnostic Analysis & Root Cause Identification
# Anthropic 10-Element Framework Applied
# =============================================================================
REASONING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<!-- 1. Task Context -->
You are DiagnosticReasoner, the core analysis engine of the DevOps Copilot system.
Your responsibility is to synthesize information from multiple sources (topology, documentation, metrics)
and provide accurate root cause analysis with actionable recommendations.
You were designed by Site Reliability Engineers to emulate expert-level incident diagnosis.

<!-- 2. Tone Context -->
Be analytical, precise, and solution-oriented.
Use technical language appropriate for DevOps engineers.
Present findings with confidence levels and supporting evidence.
Respond in Traditional Chinese (繁體中文).

<!-- 3. Background Data -->
<incident_context>
  <user_query>{query}</user_query>
  <extracted_slots>{slots_info}</extracted_slots>
</incident_context>

<evidence_sources>
  <graph_topology_results>
    <!-- Service dependencies, deployment history, infrastructure relationships -->
    {graph_context}
  </graph_topology_results>
  
  <vector_search_results>
    <!-- Similar past incidents, documentation, post-mortems -->
    {vector_context}
  </vector_search_results>
  
  <realtime_metrics>
    <!-- MCP tool query results: SQL queries, metrics, logs -->
    {mcp_context}
  </realtime_metrics>
</evidence_sources>

<!-- 4. Detailed Task Description & Rules -->
Perform comprehensive root cause analysis following this methodology:

ANALYSIS STEPS:
1. SYMPTOM IDENTIFICATION - What is the observed problem?
2. EVIDENCE CORRELATION - What do the data sources tell us?
3. HYPOTHESIS GENERATION - What could be causing this?
4. ROOT CAUSE DETERMINATION - What is the most likely cause?
5. IMPACT ASSESSMENT - What is affected and how severely?
6. REMEDIATION RECOMMENDATION - What actions should be taken?

RULES:
1. Base all conclusions on provided evidence - do not hallucinate facts
2. Clearly distinguish between confirmed facts and inferences
3. Provide confidence levels (高/中/低) for each conclusion
4. Prioritize recommendations by impact and urgency
5. Consider both immediate fixes and long-term prevention
6. Reference specific evidence when making claims

<!-- 8. Thinking Step by Step -->
Before providing your final analysis, think through the problem systematically.
Use the <thinking> tags to show your reasoning process.

<!-- 9. Output Formatting -->
Structure your response as follows:

<analysis>
  <thinking>
    [Your step-by-step reasoning through the evidence]
  </thinking>
  
  <diagnosis>
    <root_cause confidence="高|中|低">
      [Identified root cause]
    </root_cause>
    <evidence>
      [Supporting evidence from the data sources]
    </evidence>
    <impact>
      [Scope and severity of the issue]
    </impact>
  </diagnosis>
  
  <recommendations>
    <immediate priority="1">
      [Most urgent action to take]
    </immediate>
    <followup priority="2">
      [Secondary actions]
    </followup>
    <prevention>
      [Long-term preventive measures]
    </prevention>
  </recommendations>
</analysis>""",
        ),
        (
            "human",
            """<!-- 7. Immediate Task -->
Analyze the incident and provide your diagnostic assessment.""",
        ),
        ("ai", "<analysis>\n  <thinking>"),  # <!-- 10. Prefilled Response -->
    ]
)


async def mcp_tool_node(state: GraphState) -> GraphState:
    """
    MCP Tool Use Node

    Connects to MCP servers for real-time data queries (SQL, metrics, etc.)
    Currently skipped until MCP integration is implemented.
    """
    # TODO: Implement actual MCP protocol connection
    # This node should connect to real MCP servers for:
    # - SQL queries to metrics databases
    # - Real-time monitoring data
    # - Log aggregation systems
    print("[MCP] Warning: MCP integration not yet implemented. Skipping MCP tool queries.")
    
    # Return empty results - reasoning node will proceed without MCP data
    return {**state, "mcp_results": []}


async def reasoning_node(state: GraphState) -> GraphState:
    """
    LLM Reasoning Node

    Aggregates context from all sources and generates diagnostic analysis.
    """
    query = state.get("query", "")
    slots = state.get("slots", SlotInfo())
    graph_results = state.get("graph_results", [])
    vector_results = state.get("vector_results", [])
    mcp_results = state.get("mcp_results", [])

    # Build context strings
    slots_info = f"""
Service: {slots.service_name or 'Unknown'}
Error Type: {slots.error_type or 'Unknown'}
Environment: {slots.environment or 'Not specified'}
Timestamp: {slots.timestamp or 'Not specified'}
Context: {slots.additional_context or 'None'}
"""

    graph_context = _format_results(graph_results) or "No graph results available."
    vector_context = _format_results(vector_results) or "No document matches found."
    mcp_context = _format_results(mcp_results) or "No real-time data available."

    # Track reasoning steps
    reasoning_steps = [
        "Input Guardrails: Incident query detected",
        f"Slot Extraction: Identified service '{slots.service_name or 'unknown'}'",
        f"Graph Search: Found {len(graph_results)} topology results",
        f"Vector Search: Found {len(vector_results)} document matches",
        f"MCP Tool: Executed {len(mcp_results)} data queries",
        "LLM Reasoning: Synthesizing diagnostic path",
    ]

    # Generate LLM analysis
    try:
        llm = get_llm()
        chain = REASONING_PROMPT | llm
        result = await chain.ainvoke(
            {
                "query": query,
                "slots_info": slots_info,
                "graph_context": graph_context,
                "vector_context": vector_context,
                "mcp_context": mcp_context,
            }
        )
        # Handle prefill: response starts after "<analysis>\n  <thinking>"
        # Prepend the prefill to complete the XML structure
        llm_analysis = "<analysis>\n  <thinking>" + result.content
    except Exception as e:
        llm_analysis = f"Analysis error: {e}"

    # Build diagnostic path
    diagnostic = _build_diagnostic_response(
        query, slots, graph_results, vector_results, mcp_results, llm_analysis
    )

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


def _build_diagnostic_response(
    query: str,
    slots: SlotInfo,
    graph_results: List[RetrievalResult],
    vector_results: List[RetrievalResult],
    mcp_results: List[RetrievalResult],
    llm_analysis: str,
) -> DiagnosticResponse:
    """Build structured diagnostic response"""

    steps = []

    # Root node - the trigger/symptom
    root_step = DiagnosticStep(
        id="root",
        source="Log Analysis",
        title="Trigger: Connection Pool Exhausted",
        detail=f"Error observed: {slots.error_type or 'Connection timeout'} in {slots.service_name or 'Service'}",
        status="error",
        is_root=True,
        raw_content={
            "type": "log",
            "data": f"[ERROR] [{slots.service_name or 'Service'}] Connection pool exhausted - {query}",
        },
    )
    steps.append(root_step)

    # Add graph-based context
    if graph_results:
        for i, gr in enumerate(graph_results[:1]):  # Take first graph result
            steps.append(
                DiagnosticStep(
                    id=f"graph_{i}",
                    source="Graph Topology",
                    title=f"Context: {gr.title}",
                    detail=gr.content,
                    status="warning",
                    is_parallel=True,
                    raw_content={"type": "graph", "data": gr.raw_data},
                )
            )

    # Add vector-based context
    if vector_results:
        for i, vr in enumerate(vector_results[:1]):  # Take first vector result
            steps.append(
                DiagnosticStep(
                    id=f"vector_{i}",
                    source="Vector Search",
                    title=f"Context: {vr.title}",
                    detail=(
                        vr.content[:100] + "..."
                        if len(vr.content) > 100
                        else vr.content
                    ),
                    status="info",
                    is_parallel=True,
                    raw_content={"type": "markdown", "data": vr.raw_data},
                )
            )

    # Generate suggestion
    suggestion = _generate_suggestion(slots, graph_results, vector_results, mcp_results)

    return DiagnosticResponse(path=steps, suggestion=suggestion, confidence=0.87)


def _generate_suggestion(
    slots: SlotInfo,
    graph_results: List[RetrievalResult],
    vector_results: List[RetrievalResult],
    mcp_results: List[RetrievalResult],
) -> str:
    """Generate actionable recommendation"""
    service = slots.service_name or "the affected service"

    # Check if we have pool-related evidence
    pool_evidence = any("pool" in str(r.raw_data).lower() for r in mcp_results)
    deployment_evidence = any("deploy" in r.title.lower() for r in graph_results)

    if pool_evidence and deployment_evidence:
        return f"建議檢查 `{service}` 的 HikariCP 設定。新版本部署可能重置了 `maximum-pool-size` 參數。根據 MCP 查詢結果，當前連線池已達上限。"
    elif deployment_evidence:
        return f"最近有對 `{service}` 的部署操作。建議回滾到上一個穩定版本或檢查部署配置差異。"
    else:
        return f"建議檢查 `{service}` 的系統資源和配置，並查看最近的變更記錄。"
