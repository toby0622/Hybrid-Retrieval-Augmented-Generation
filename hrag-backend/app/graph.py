from app.nodes.feedback import feedback_node, route_after_feedback
from app.nodes.input_guard import input_guard_node, route_after_guard
from app.nodes.mcp_tools import mcp_tool_node
from app.nodes.reasoning import reasoning_node
from app.nodes.response import (chat_response_node,
                                clarification_response_node,
                                diagnostic_response_node,
                                end_conversation_node)
from app.nodes.retrieval import hybrid_retrieval_node
from app.nodes.slot_filling import route_after_slot_check, slot_check_node
from app.state import GraphState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


def create_hrag_graph() -> StateGraph:
    workflow = StateGraph(GraphState)

    workflow.add_node("input_guard", input_guard_node)
    workflow.add_node("slot_check", slot_check_node)
    workflow.add_node("ask_clarification", clarification_response_node)
    workflow.add_node("retrieval", hybrid_retrieval_node)
    workflow.add_node("mcp_tool", mcp_tool_node)
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("chat_response", chat_response_node)
    workflow.add_node("diagnostic_response", diagnostic_response_node)
    workflow.add_node("feedback", feedback_node)
    workflow.add_node("end_conversation", end_conversation_node)

    workflow.set_entry_point("input_guard")

    workflow.add_conditional_edges(
        "input_guard",
        route_after_guard,
        {
            "chat_response": "chat_response",
            "slot_check": "slot_check",
            "end": "end_conversation",
        },
    )

    workflow.add_edge("chat_response", END)

    workflow.add_conditional_edges(
        "slot_check",
        route_after_slot_check,
        {"ask_clarification": "ask_clarification", "retrieval": "retrieval"},
    )

    workflow.add_edge("ask_clarification", END)

    workflow.add_edge("retrieval", "mcp_tool")
    workflow.add_edge("mcp_tool", "reasoning")
    workflow.add_edge("reasoning", "diagnostic_response")

    workflow.add_edge("diagnostic_response", END)

    workflow.add_conditional_edges(
        "feedback",
        route_after_feedback,
        {
            "slot_check": "slot_check",
            "end": "end_conversation",
        },
    )

    workflow.add_edge("end_conversation", END)

    return workflow


def compile_graph(with_checkpointer: bool = True):
    workflow = create_hrag_graph()

    if with_checkpointer:
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


graph = compile_graph(with_checkpointer=True)


async def run_query(
    query: str, thread_id: str = "default", feedback: str = None
) -> GraphState:
    config = {"configurable": {"thread_id": thread_id}}

    # Try to get existing state from MemorySaver
    existing_state = None
    try:
        state_snapshot = graph.get_state(config)
        if state_snapshot and state_snapshot.values:
            existing_state = state_snapshot.values
    except Exception:
        pass

    # Check if we're in a clarification flow (awaiting user response)
    is_clarification_response = (
        existing_state 
        and existing_state.get("awaiting_clarification", False)
    )

    if is_clarification_response:
        # This is a clarification response - merge with existing state
        initial_state: GraphState = {
            "query": query,
            "messages": existing_state.get("messages", []),
            # Preserve context from previous state
            "domain": existing_state.get("domain"),
            "intent": existing_state.get("intent"),
            "slots": existing_state.get("slots"),
            "original_query": existing_state.get("original_query"),
            "clarification_count": existing_state.get("clarification_count", 0),
            # Mark that we're processing a clarification response
            "awaiting_clarification": False,
            # Pass the clarification response for slot merging
            "clarification_response": query,
        }
    else:
        # Fresh query - create new state
        initial_state: GraphState = {
            "query": query,
            "messages": [],
            "clarification_count": 0,
            "awaiting_clarification": False,
            "original_query": query,  # Save original query
        }

    if feedback:
        initial_state["feedback"] = feedback

    result = await graph.ainvoke(initial_state, config)

    return result
