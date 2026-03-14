"""Conversation API endpoints - v2.0 deep interaction system."""

from fastapi import APIRouter, HTTPException, Query

from app.models.schema import (
    ConversationStartRequest,
    ConversationStartResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationMessage,
)
from app.services.conversation import (
    start_conversation,
    send_message,
    get_conversation,
    list_conversations,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/start", response_model=ConversationStartResponse)
async def api_start_conversation(request: ConversationStartRequest):
    """Start a new conversation session."""
    try:
        conversation_id = await start_conversation(
            analysis_id=request.analysis_id,
            mode=request.mode.value,
            persona_ids=request.persona_ids,
            topic=request.topic,
        )
        return ConversationStartResponse(conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(500, f"Failed to start conversation: {str(e)}")


@router.post("/{conversation_id}/message", response_model=ConversationMessageResponse)
async def api_send_message(conversation_id: str, request: ConversationMessageRequest):
    """Send a message and get response(s) from virtual personas."""
    try:
        responses = await send_message(conversation_id, request.content)
        messages = [
            ConversationMessage(
                role=r["role"],
                persona_id=r.get("persona_id"),
                content=r["content"],
            )
            for r in responses
        ]
        return ConversationMessageResponse(messages=messages)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to process message: {str(e)}")


@router.get("/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    """Get a conversation with full history."""
    try:
        return await get_conversation(conversation_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("s")
async def api_list_conversations(analysis_id: str = Query(...)):
    """List all conversations for an analysis."""
    return await list_conversations(analysis_id)
