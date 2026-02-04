from typing import List

from app.core.config import settings
from app.nodes.retrieval import _make_serializable
from app.services.mcp import MCPDatabaseClient, MCPTools
from app.state import DynamicSlotInfo, GraphState, RetrievalResult, SlotInfo


async def mcp_tool_node(state: GraphState) -> GraphState:
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
            metrics, metrics_query = await MCPTools.query_service_metrics(
                service_name, limit=5
            )
            for m in metrics:
                m_with_query = _make_serializable(m.copy())
                m_with_query["sql_query"] = metrics_query
                m_serializable = _make_serializable(m)
                results.append(
                    RetrievalResult(
                        source="mcp_tool",
                        title=f"Metric: {m.get('metric_name', 'Unknown')}",
                        content=f"Service: {m.get('service_name')}\n"
                        f"Value: {m.get('metric_value')} {m.get('unit', '')}\n"
                        f"Time: {m.get('timestamp')}",
                        metadata=m_with_query,
                        confidence=0.95,
                        raw_data=m_serializable,
                    ).model_dump()
                )

            health, health_query = await MCPTools.get_service_health(service_name)
            for h in health:
                h_with_query = _make_serializable(h.copy())
                h_with_query["sql_query"] = health_query
                h_serializable = _make_serializable(h)
                status = h.get("health_status", "unknown")
                status_emoji = (
                    "✅"
                    if status == "healthy"
                    else "⚠️" if status == "degraded" else "❌"
                )
                results.append(
                    RetrievalResult(
                        source="mcp_tool",
                        title=f"Health Status: {status_emoji} {status.upper()}",
                        content=f"Service: {h.get('service_name')}\n"
                        f"Status: {status}\n"
                        f"Last Check: {h.get('last_check')}\n"
                        f"Details: {h.get('details', 'N/A')}",
                        metadata=h_with_query,
                        confidence=0.98,
                        raw_data=h_serializable,
                    ).model_dump()
                )

        log_level = "error" if error_type else None
        logs, logs_query = await MCPTools.query_service_logs(
            service_name=service_name, log_level=log_level, limit=5
        )
        for log in logs:
            log_with_query = _make_serializable(log.copy())
            log_with_query["sql_query"] = logs_query
            log_serializable = _make_serializable(log)
            level = log.get("log_level", "info").upper()
            results.append(
                RetrievalResult(
                    source="mcp_tool",
                    title=f"Log [{level}]: {log.get('service_name', 'Unknown')}",
                    content=f"Level: {level}\n"
                    f"Message: {log.get('message', '')}\n"
                    f"Time: {log.get('timestamp')}",
                    metadata=log_with_query,
                    confidence=0.90,
                    raw_data=log_serializable,
                ).model_dump()
            )

    except Exception as e:
        print(f"[MCP] Tool execution error: {e}")

    return {**state, "mcp_results": results}
