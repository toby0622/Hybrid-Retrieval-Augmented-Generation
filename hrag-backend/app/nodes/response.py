"""
Response Generation Node
Formats the final response for the user
"""

from app.state import GraphState, Message, DiagnosticResponse


async def chat_response_node(state: GraphState) -> GraphState:
    """
    Generate response for chat/greeting messages
    """
    query = state.get("query", "").lower()
    
    if any(kw in query for kw in ["hello", "hi", "hey"]):
        response = "Hello! I am your DevOps Copilot. I can help investigate incidents, analyze logs, and query the Knowledge Graph. Please provide specific error logs or incident details to start."
    elif "help" in query or "what" in query:
        response = """I'm a DevOps incident response assistant. I can help you:

• **Investigate incidents** - Describe an error or issue you're seeing
• **Analyze logs** - Paste error logs or symptoms
• **Query knowledge base** - Search past incidents and documentation
• **Find root causes** - Cross-reference topology with historical data

Just describe your issue and I'll help diagnose it!"""
    else:
        response = "I'm here to help with DevOps incidents and troubleshooting. Could you describe the issue you're experiencing?"
    
    return {
        **state,
        "response": response
    }


async def clarification_response_node(state: GraphState) -> GraphState:
    """
    Generate clarification question response
    """
    clarification = state.get("clarification_question", "")
    
    return {
        **state,
        "response": clarification
    }


async def diagnostic_response_node(state: GraphState) -> GraphState:
    """
    Format diagnostic response for presentation
    """
    diagnostic = state.get("diagnostic")
    reasoning_steps = state.get("reasoning_steps", [])
    
    if not diagnostic:
        return {
            **state,
            "response": "Unable to generate diagnostic analysis. Please provide more details."
        }
    
    # Build formatted response
    response_parts = []
    
    # Add reasoning summary
    response_parts.append("## Analysis Complete\n")
    response_parts.append(f"根據混合檢索與日誌分析，發現潛在根因。\n")
    
    # Response will be enhanced by the diagnostic card in frontend
    response = "\n".join(response_parts)
    
    return {
        **state,
        "response": response
    }


async def end_conversation_node(state: GraphState) -> GraphState:
    """
    Handle conversation end
    """
    return {
        **state,
        "response": "Thank you for using DevOps Copilot. The conversation has ended. Feel free to start a new conversation anytime!"
    }
