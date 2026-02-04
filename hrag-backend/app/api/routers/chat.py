import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.graph import run_query
from app.core.logger import logger
from app.schemas.chat import ChatRequest, ChatResponse, ReasoningStep

router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())

    async def generate() -> AsyncGenerator[str, None]:
        reasoning_steps = [
            {
                "id": "step_0",
                "label": "Input Guardrails: Analyzing query...",
                "status": "pending",
            },
            {
                "id": "step_1",
                "label": "Slot Extraction: Identifying entities...",
                "status": "pending",
            },
            {
                "id": "step_2",
                "label": "Graph Search: Querying topology...",
                "status": "pending",
            },
            {
                "id": "step_3",
                "label": "Vector Search: Finding relevant documents...",
                "status": "pending",
            },
            {
                "id": "step_4",
                "label": "MCP Tool: Executing data queries...",
                "status": "pending",
            },
            {
                "id": "step_5",
                "label": "LLM Reasoning: Synthesizing diagnosis...",
                "status": "pending",
            },
        ]

        for i, step in enumerate(reasoning_steps):
            step["status"] = "active"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"
            await asyncio.sleep(0.3)

            step["status"] = "completed"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"

        try:
            result = await run_query(
                query=request.query, thread_id=thread_id, feedback=request.feedback
            )

            response_data = {
                "type": "complete",
                "thread_id": thread_id,
                "response": result.get("response", ""),
                "intent": result.get("intent", "chat"),
                "diagnostic": result.get("diagnostic"),
                "clarification_question": result.get("clarification_question"),
            }

            if response_data["diagnostic"]:
                response_data["diagnostic"] = response_data["diagnostic"].model_dump()

            yield f"data: {json.dumps(response_data)}\n\n"

        except Exception as e:
            logger.exception("Error in chat stream generation")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal Server Error'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())

    try:
        result = await run_query(
            query=request.query, thread_id=thread_id, feedback=request.feedback
        )

        intent = result.get("intent", "chat")
        response = result.get("response", "")
        diagnostic = result.get("diagnostic")
        reasoning_steps = result.get("reasoning_steps", [])
        clarification = result.get("clarification_question")

        if diagnostic:
            response_type = "diagnostic"
        elif reasoning_steps:
            response_type = "reasoning"
        elif clarification:
            response_type = "clarification"
        else:
            response_type = "text"

        formatted_steps = [
            ReasoningStep(id=f"step_{i}", label=step, status="completed")
            for i, step in enumerate(reasoning_steps)
        ]

        return ChatResponse(
            thread_id=thread_id,
            response=response if not clarification else clarification,
            intent=intent,
            response_type=response_type,
            reasoning_steps=formatted_steps if formatted_steps else None,
            diagnostic=diagnostic,
            clarification_question=clarification,
        )

    except Exception as e:
        logger.exception(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
