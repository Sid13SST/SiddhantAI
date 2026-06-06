import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
# pyrefly: ignore [missing-import]
import httpx

# We will test the routes locally by importing and calling the services/engines directly,
# as well as mocking the HTTP requests.
from app.core.config import settings
settings.OPENROUTER_API_KEY = ""
from app.services.voice_service import VoiceConfidenceRecovery, VoiceQueryRouter, TranscriptStorageService, SUMMARIES_PATH
from app.services.booking_orchestrator import BookingOrchestrator

async def run_voice_tests():
    print("=== STARTING VOICE AGENT LAYER INTEGRATION TESTS ===")

    # Test Case 1: Fuzzy Phonetic Recovery Matcher
    print("\n[Test Case 1] Phonetic Typo Recovery...")
    queries = [
        ("tell me about grad onion", "Gradonix"),
        ("what is friction ai", "FrictaAI"),
        ("how to use fast api", "FastAPI"),
        ("explain next js features", "Next.js"),
        ("siddharth profile details", "Siddhant")
    ]
    
    for input_q, expected_target in queries:
        corrected, suggestion = VoiceConfidenceRecovery.recover_query(input_q)
        print(f"  Input: '{input_q}' -> Corrected: '{corrected}' (Suggestion: {suggestion})")
        assert expected_target in corrected, f"Expected '{expected_target}' to be restored in corrected query!"
    print("[OK] Fuzzy Phonetic Recovery Matcher passes.")

    # Test Case 2: Voice Query Completions Routing (Stateless RAG QA)
    print("\n[Test Case 2] Voice Query Routing & QA Integration...")
    test_call_id = "test_call_voice_12345"
    
    # Simulate first turn
    query1 = "Tell me about grad onion"
    result1 = await VoiceQueryRouter.route_voice_query(query1, test_call_id)
    print(f"  Query: '{query1}'")
    print(f"  Answer: '{result1['answer'][:150]}...'")
    print(f"  Active Topic: '{result1['active_topic']}'")
    assert "Gradonix" in result1["answer"] or "calendar" in result1["answer"].lower(), "Answer should contain details about Gradonix!"
    assert result1["active_topic"] == "Gradonix Project"

    # Test Case 3: Follow-Up Context Memory
    print("\n[Test Case 3] Multi-turn Follow-up Context...")
    # Follow-up asking about technologies mentioned in the previous turn
    query2 = "What technologies does it use?"
    result2 = await VoiceQueryRouter.route_voice_query(query2, test_call_id)
    print(f"  Follow-up Query: '{query2}'")
    print(f"  Answer: '{result2['answer'][:150]}...'")
    assert any(tech in result2["answer"] for tech in ["Python", "FastAPI", "Next.js", "React", "Node.js", "PostgreSQL", "SpringBoot"]), "Should mention Gradonix tech stack!"

    # Test Case 4: Booking Conversational Integration via Voice
    print("\n[Test Case 4] Voice Booking Intent Routing...")
    booking_call_id = "booking_call_voice_9999"
    
    # Turn 1: Intent triggering
    b_query1 = "I want to schedule an interview"
    b_result1 = await VoiceQueryRouter.route_voice_query(b_query1, booking_call_id)
    print(f"  User: '{b_query1}'")
    print(f"  Agent: '{b_result1['answer']}'")
    assert "timezone" in b_result1["answer"].lower(), "Agent should ask for timezone!"
    
    # Turn 2: Timezone input
    b_query2 = "IST"
    b_result2 = await VoiceQueryRouter.route_voice_query(b_query2, booking_call_id)
    print(f"  User: '{b_query2}'")
    print(f"  Agent: '{b_result2['answer']}'")
    assert "email" in b_result2["answer"].lower(), "Agent should ask for email!"

    # Test Case 5: End-of-call Summary Generation
    print("\n[Test Case 5] Call End Summary Generation Webhook...")
    
    # Set mock flags in session cache to simulate completed booking
    session = BookingOrchestrator.SESSION_CACHE.get(booking_call_id, {})
    session["last_booking_created"] = True
    session["last_booking_id"] = "evt_mock_cal_12345"
    BookingOrchestrator.update_session(booking_call_id, session)
    
    # Simulate webhook call-end parsing
    history = [
        {"role": "user", "content": "I want to schedule an interview"},
        {"role": "assistant", "content": "Sure, what timezone?"},
        {"role": "user", "content": "IST"},
        {"role": "assistant", "content": "Great. What is your email?"}
    ]
    
    # Trigger summary generator
    summary = TranscriptStorageService.generate_call_summary(
        call_id=booking_call_id,
        duration=185.4, # 3m 5s
        history=history
    )
    
    print("  Generated Call Summary:")
    print(json.dumps(summary, indent=4))
    
    assert summary["call_duration"] == "3m 5s", "Duration formatting should match!"
    assert summary["booking_created"] is True, "Booking created flag should be tracked!"
    assert summary["booking_id"] == "evt_mock_cal_12345", "Booking ID should be tracked!"
    assert "Interview Availability" in summary["topics_discussed"], "Should extract scheduling topic!"
    
    # Check filesystem
    assert SUMMARIES_PATH.exists(), "call_summaries.json file must be created!"
    print("[OK] Call summary serialized successfully on disk.")

    print("\n=== ALL VOICE AGENT LAYER INTEGRATION TESTS PASSED ===")

if __name__ == "__main__":
    asyncio.run(run_voice_tests())
