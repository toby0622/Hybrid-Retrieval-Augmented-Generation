"""
HRAG LangGraph Main Graph Assembly
Constructs the complete workflow graph from nodes
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import GraphState
from app.nodes.input_guard import input_guard_node, route_after_guard
from app.nodes.slot_filling import slot_check_node, route_after_slot_check
from app.nodes.retrieval import hybrid_retrieval_node
from app.nodes.reasoning import mcp_tool_node, reasoning_node
from app.nodes.response import (
    chat_response_node,
    clarification_response_node,
    diagnostic_response_node,
    end_conversation_node
)
from app.nodes.feedback import feedback_node, route_after_feedback


def create_hrag_graph() -> StateGraph:
    """
    Create the complete HRAG workflow graph.
    
    Flow:
    1. Input Guard → routes to chat/incident/end
    2. Slot Check → generates clarification or proceeds
    3. Hybrid Retrieval → parallel graph + vector search
    4. MCP Tool → external data queries
    5. Reasoning → LLM analysis
    6. Response → format output
    7. Feedback → handle user feedback, case study generation
    """
    
    # Initialize graph with state schema
    workflow = StateGraph(GraphState)
    
    # Add nodes
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
    
    # Set entry point
    workflow.set_entry_point("input_guard")
    
    # Add conditional edges from input guard
    workflow.add_conditional_edges(
        "input_guard",
        route_after_guard,
        {
            "chat_response": "chat_response",
            "slot_check": "slot_check",
            "end": "end_conversation"
        }
    )
    
    # Chat response → END
    workflow.add_edge("chat_response", END)
    
    # Slot check → clarification or retrieval
    workflow.add_conditional_edges(
        "slot_check",
        route_after_slot_check,
        {
            "ask_clarification": "ask_clarification",
            "retrieval": "retrieval"
        }
    )
    
    # Clarification → END (waits for user response)
    workflow.add_edge("ask_clarification", END)
    
    # Retrieval → MCP Tool → Reasoning → Response
    workflow.add_edge("retrieval", "mcp_tool")
    workflow.add_edge("mcp_tool", "reasoning")
    workflow.add_edge("reasoning", "diagnostic_response")
    
    # Diagnostic response → END (waits for feedback)
    workflow.add_edge("diagnostic_response", END)
    
    # Feedback handling
    workflow.add_conditional_edges(
        "feedback",
        route_after_feedback,
        {
            "slot_check": "slot_check",  # More info requested
            "end": "end_conversation"     # Resolved or ended
        }
    )
    
    # End conversation → END
    workflow.add_edge("end_conversation", END)
    
    return workflow


def compile_graph(with_checkpointer: bool = True):
    """
    Compile the graph with optional checkpointer for state persistence.
    """
    workflow = create_hrag_graph()
    
    if with_checkpointer:
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    
    return workflow.compile()


# Create default compiled graph
graph = compile_graph(with_checkpointer=True)


async def run_query(
    query: str,
    thread_id: str = "default",
    feedback: str = None
) -> GraphState:
    """
    Run a query through the graph.
    
    Args:
        query: User query text
        thread_id: Conversation thread ID for state persistence
        feedback: Optional feedback from previous turn
    
    Returns:
        Final graph state with response
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state: GraphState = {
        "query": query,
        "messages": [],
        "clarification_count": 0,
    }
    
    if feedback:
        initial_state["feedback"] = feedback
    
    result = await graph.ainvoke(initial_state, config)
    
    return result
