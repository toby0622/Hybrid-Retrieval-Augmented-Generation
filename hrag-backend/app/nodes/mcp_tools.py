"""
MCP Tool Node for LangGraph Workflow.

This node executes MCP database queries based on extracted slots
and adds the results to the graph state for use in reasoning.
"""

from typing import List

from app.mcp_client import MCPDatabaseClient, MCPTools
from app.state import DynamicSlotInfo, GraphState, RetrievalResult, SlotInfo
from config import settings


async def mcp_tool_node(state: GraphState) -> GraphState:
    """
    Execute MCP tools to fetch real-time data.
    
    This node is called after hybrid retrieval to supplement
    graph and vector search results with live database data.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with mcp_results
    """
    if not settings.mcp_enabled:
        return {**state, "mcp_results": []}
    
    is_available = await MCPDatabaseClient.is_available()
    if not is_available:
        return {**state, "mcp_results": []}
    
    slots = state.get("slots")
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()
    
    results: List[dict] = []
    filled_slots = slots.get_filled_slots()
    
    service_name = filled_slots.get("service_name")
    error_type = filled_slots.get("error_type")
    
    try:
        if service_name:
            metrics = await MCPTools.query_service_metrics(service_name, limit=5)
            for m in metrics:
                results.append(
                    RetrievalResult(
                        source="mcp_tool",
                        title=f"Metric: {m.get('metric_name', 'Unknown')}",
                        content=f"Service: {m.get('service_name')}\n"
                                f"Value: {m.get('metric_value')} {m.get('unit', '')}\n"
                                f"Time: {m.get('timestamp')}",
                        metadata=m,
                        confidence=0.95,
                        raw_data=m,
                    ).model_dump()
                )
            
            health = await MCPTools.get_service_health(service_name)
            for h in health:
                status = h.get("health_status", "unknown")
                status_emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
                results.append(
                    RetrievalResult(
                        source="mcp_tool",
                        title=f"Health Status: {status_emoji} {status.upper()}",
                        content=f"Service: {h.get('service_name')}\n"
                                f"Status: {status}\n"
                                f"Last Check: {h.get('last_check')}\n"
                                f"Details: {h.get('details', 'N/A')}",
                        metadata=h,
                        confidence=0.98,
                        raw_data=h,
                    ).model_dump()
                )
        
        log_level = "error" if error_type else None
        logs = await MCPTools.query_service_logs(
            service_name=service_name,
            log_level=log_level,
            limit=5
        )
        for log in logs:
            level = log.get("log_level", "info").upper()
            results.append(
                RetrievalResult(
                    source="mcp_tool",
                    title=f"Log [{level}]: {log.get('service_name', 'Unknown')}",
                    content=f"Level: {level}\n"
                            f"Message: {log.get('message', '')}\n"
                            f"Time: {log.get('timestamp')}",
                    metadata=log,
                    confidence=0.90,
                    raw_data=log,
                ).model_dump()
            )
    
    except Exception as e:
        print(f"[MCP] Tool execution error: {e}")
    
    return {**state, "mcp_results": results}
