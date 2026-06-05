import uuid
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request, HTTPException, Header
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from app.services.voice_service import VapiService, VoiceQueryRouter, VoiceSessionManager
from app.services.booking_orchestrator import BookingOrchestrator
from app.core.logging import logger

router = APIRouter()

class OpenAICompletionMessage(BaseModel):
    role: str
    content: str

class OpenAICompletionsRequest(BaseModel):
    model: str
    messages: List[OpenAICompletionMessage]
    temperature: Optional[float] = 0.0
    stream: Optional[bool] = False

@router.post("/query")
async def voice_query_completion(
    request: Request,
    payload: OpenAICompletionsRequest,
    x_vapi_call_id: Optional[str] = Header(None, alias="x-vapi-call-id"),
    X_Vapi_Call_Id: Optional[str] = Header(None, alias="X-Vapi-Call-Id")
):
    """OpenAI-compatible completions endpoint that Vapi calls as its Custom LLM.
    
    Translates user speech query into grounded QA / Booking answers.
    """
    # 1. Resolve unique session call ID
    call_id = x_vapi_call_id or X_Vapi_Call_Id
    if not call_id:
        # Fallback for testing/direct curl requests
        call_id = f"voice_{uuid.uuid4().hex[:12]}"
        
    logger.info(f"Voice Query Completion: call_id={call_id}, model={payload.model}")
    
    # 2. Extract latest user transcript utterance
    user_msgs = [m for m in payload.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="Completions request must contain at least one user message.")
        
    latest_query = user_msgs[-1].content
    logger.info(f"Voice query user query: '{latest_query}'")
    
    # 3. Route query through Voice Agent layer
    result = await VoiceQueryRouter.route_voice_query(latest_query, call_id)
    answer = result["answer"]
    suggestion = result["suggestion"]
    
    # If suggestion was generated (e.g. did you mean...), prepend it politely
    final_voice_answer = answer
    if suggestion:
        final_voice_answer = f"{suggestion}. {answer}"
        
    # 4. Return standard OpenAI completions payload structure
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time() if hasattr(time, 'time') else 1700000000),
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": final_voice_answer
                },
                "finish_reason": "stop"
            }
        ]
    }

@router.post("/webhook")
async def voice_webhook(request: Request):
    """Processes Vapi webhook callbacks (assistant-request and end-of-call-report)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
        
    return await VapiService.process_webhook_event(payload)

@router.get("/session")
async def get_voice_session(session_id: str):
    """Returns the details of a voice session (topics, booking context details, history)."""
    session = BookingOrchestrator.SESSION_CACHE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found or already closed.")
        
    return {
        "session_id": session_id,
        "active_topic": session.get("active_topic", "General QA"),
        "booking_context": {
            "step": session.get("step"),
            "action": session.get("action"),
            "timezone": session.get("timezone"),
            "email": session.get("email"),
            "topic": session.get("topic")
        },
        "history": session.get("voice_history", [])
    }

# Make sure time is imported for completions timestamp
import time
