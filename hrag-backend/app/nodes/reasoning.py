"""
LLM Reasoning Node
Context aggregation, tool use simulation, and diagnostic path generation
"""

from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from app.state import (
    GraphState, RetrievalResult, DiagnosticResponse, 
    DiagnosticStep, SlotInfo
)


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.2,
    )


REASONING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a DevOps incident analysis expert. Analyze the following information and provide a diagnosis.

## User Query
{query}

## Extracted Information
{slots_info}

## Graph Database Results (Topology & Relationships)
{graph_context}

## Vector Search Results (Documentation & Post-Mortems)
{vector_context}

## MCP Tool Results (Real-time Data)
{mcp_context}

Based on this information:
1. Identify the most likely root cause
2. Trace the diagnostic path from symptoms to cause
3. Provide specific recommended actions

Format your response as a structured analysis."""),
    ("human", "Provide your diagnosis.")
])


async def mcp_tool_node(state: GraphState) -> GraphState:
    """
    MCP Tool Use Node
    
    Simulates MCP protocol calls to external tools (SQL queries, metrics, etc.)
    In production, this would connect to actual MCP servers.
    """
    slots = state.get("slots", SlotInfo())
    
    # Simulate MCP tool call results
    mcp_results: List[RetrievalResult] = []
    
    # Mock SQL query result
    if slots.service_name:
        mcp_results.append(RetrievalResult(
            source="mcp_tool",
            title="SQL Query: Connection Metrics",
            content=f"""SELECT avg(pool_size), max(wait_time) FROM metrics 
WHERE service='{slots.service_name}' AND timestamp > NOW() - INTERVAL '1 hour'
Result: avg_pool=8, max_wait=4523ms""",
            metadata={
                "tool": "sql_query",
                "database": "metrics_db"
            },
            confidence=0.95,
            raw_data={
                "avg_pool_size": 8,
                "max_wait_time_ms": 4523,
                "active_connections": 10,
                "max_pool_size": 10
            }
        ))
    
    return {
        **state,
        "mcp_results": mcp_results
    }


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
        "LLM Reasoning: Synthesizing diagnostic path"
    ]
    
    # Generate LLM analysis
    try:
        llm = get_llm()
        chain = REASONING_PROMPT | llm 
        result = await chain.ainvoke({
            "query": query,
            "slots_info": slots_info,
            "graph_context": graph_context,
            "vector_context": vector_context,
            "mcp_context": mcp_context
        })
        llm_analysis = result.content
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
        "aggregated_context": f"{graph_context}\n\n{vector_context}\n\n{mcp_context}"
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
    llm_analysis: str
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
            "data": f"[ERROR] [{slots.service_name or 'Service'}] Connection pool exhausted - {query}"
        }
    )
    steps.append(root_step)
    
    # Add graph-based context
    if graph_results:
        for i, gr in enumerate(graph_results[:1]):  # Take first graph result
            steps.append(DiagnosticStep(
                id=f"graph_{i}",
                source="Graph Topology",
                title=f"Context: {gr.title}",
                detail=gr.content,
                status="warning",
                is_parallel=True,
                raw_content={
                    "type": "graph",
                    "data": gr.raw_data
                }
            ))
    
    # Add vector-based context  
    if vector_results:
        for i, vr in enumerate(vector_results[:1]):  # Take first vector result
            steps.append(DiagnosticStep(
                id=f"vector_{i}",
                source="Vector Search",
                title=f"Context: {vr.title}",
                detail=vr.content[:100] + "..." if len(vr.content) > 100 else vr.content,
                status="info",
                is_parallel=True,
                raw_content={
                    "type": "markdown",
                    "data": vr.raw_data
                }
            ))
    
    # Generate suggestion
    suggestion = _generate_suggestion(slots, graph_results, vector_results, mcp_results)
    
    return DiagnosticResponse(
        path=steps,
        suggestion=suggestion,
        confidence=0.87
    )


def _generate_suggestion(
    slots: SlotInfo,
    graph_results: List[RetrievalResult],
    vector_results: List[RetrievalResult],
    mcp_results: List[RetrievalResult]
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
