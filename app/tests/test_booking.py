import asyncio
import os
import json
import datetime
from pathlib import Path
from app.models.qa import QARequest
from app.services.timezone_service import TimezoneService
from app.services.calendar_service import CalendarService
from app.services.booking_engine import AvailabilityEngine, SlotRecommendationService
from app.services.booking_orchestrator import BookingOrchestrator
from app.services.qa_engine import QAEngine
from app.core.config import settings
settings.OPENROUTER_API_KEY = ""
from app.core.logging import logger

logger.info("Initializing Booking & Calendar Layer integration tests...")

async def run_booking_tests():
    # Make sure we point DATA_DIR to a temporary location to run clean tests
    original_data_dir = settings.DATA_DIR
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        settings.DATA_DIR = tmpdir
        logger.info(f"Using temp DATA_DIR for tests: {tmpdir}")
        
        calendar_service = CalendarService()
        calendar_service.use_real_cal = False # Force mock sandbox mode for deterministic testing!
        calendar_service.mock_file = Path(tmpdir) / "mock_calendar.json"
        
        # 1. Test Timezone normalization and formatting
        logger.info("\n--- Test Case 1: Timezone Normalization ---")
        dt_utc = TimezoneService.normalize_to_utc("2026-06-08T10:00:00")
        assert dt_utc.tzname() == "UTC"
        
        # Test friendly format (should display specific date since it's far in future)
        friendly_ist = TimezoneService.format_friendly_time(dt_utc, "IST")
        logger.info(f"Friendly format IST: '{friendly_ist}'")
        assert "IST" in friendly_ist
        
        friendly_est = TimezoneService.format_friendly_time(dt_utc, "EST")
        logger.info(f"Friendly format EST: '{friendly_est}'")
        assert "EST" in friendly_est
        
        # 2. Test Slot Generation and Buffer Filtering
        logger.info("\n--- Test Case 2: Slot Generation with Buffers ---")
        # Let's seed a mock busy slot on 2026-06-08 from 10:00 to 11:00 UTC (15:30 to 16:30 IST)
        busy_start = TimezoneService.normalize_to_utc("2026-06-08T10:00:00")
        busy_end = TimezoneService.normalize_to_utc("2026-06-08T11:00:00")
        
        calendar_service.create_event(
            title="Existing Busy Event",
            start=busy_start,
            end=busy_end,
            email="other@example.com",
            description="Busy"
        )
        
        # Generate availability for target date 2026-06-08 in IST
        available_slots = AvailabilityEngine.get_available_slots(
            target_tz_name="IST",
            duration_minutes=30,
            date_range_days=7, # scans next 7 days (ensure 2026-06-08 is covered or scan from target date)
            calendar_service=calendar_service
        )
        
        # Let's verify that no generated slot overlaps with the buffered busy range:
        # [busy_start - 15m, busy_end + 15m] => [09:45, 11:15] UTC
        buffer_start = busy_start - datetime.timedelta(minutes=15)
        buffer_end = busy_end + datetime.timedelta(minutes=15)
        
        for slot in available_slots:
            slot_end = slot + datetime.timedelta(minutes=30)
            overlap = slot_end > buffer_start and slot < buffer_end
            assert not overlap, f"Slot {slot} overlaps with buffered busy range [{buffer_start}, {buffer_end}]"
            
        logger.info("Successfully verified that busy slots and buffers are ignored in slot generation.")

        # 3. Test Slot Ranking and Friendly Outputs
        logger.info("\n--- Test Case 3: Slot Ranking and Friendly Outputs ---")
        ranked = SlotRecommendationService.rank_slots(available_slots, "EST")
        logger.info(f"Top 5 ranked slots in EST: {json.dumps(ranked[:2], indent=2)}")
        assert len(ranked) > 0
        assert "display" in ranked[0]
        assert "utc" in ranked[0]
        assert "EST" in ranked[0]["display"]

        # 4. Test Event Creation and Professional Description Metadata
        logger.info("\n--- Test Case 4: Event Creation & Description Metadata ---")
        event_start = TimezoneService.normalize_to_utc("2026-06-09T14:00:00")
        event_end = event_start + datetime.timedelta(minutes=30)
        
        email = "candidate@example.com"
        topic = "AI Engineering Internship discussion"
        title = "Scaler Interview - Siddhant"
        description = (
            f"Booked Through:\nSiddhant's AI Representative\n\n"
            f"Candidate Email:\n{email}\n\n"
            f"Discussion Topic:\n{topic}\n\n"
            f"Created:\n{datetime.datetime.now(datetime.timezone.utc).isoformat()}Z"
        )
        
        event = calendar_service.create_event(
            title=title,
            start=event_start,
            end=event_end,
            email=email,
            description=description
        )
        
        assert event["id"] is not None
        assert email in event["description"]
        assert topic in event["description"]
        assert "Booked Through:" in event["description"]
        logger.info("Event successfully created with structured description metadata.")

        # 5. Test Double Booking Prevention Locks
        logger.info("\n--- Test Case 5: Double Booking Prevention Locks ---")
        slot_to_book = "2026-06-10T10:00:00Z"
        
        # Trigger concurrent bookings
        async def book_attempt_1():
            return await BookingOrchestrator._lock_and_book_slot(
                start_time_str=slot_to_book,
                duration_minutes=30,
                email="candidate1@example.com",
                topic="Role A",
                timezone="IST",
                calendar_service=calendar_service
            )

        async def book_attempt_2():
            return await BookingOrchestrator._lock_and_book_slot(
                start_time_str=slot_to_book,
                duration_minutes=30,
                email="candidate2@example.com",
                topic="Role B",
                timezone="IST",
                calendar_service=calendar_service
            )

        # Run them in parallel using asyncio.gather
        res1, res2 = await asyncio.gather(book_attempt_1(), book_attempt_2())
        
        # One must succeed and the other must fail
        successes = [r[0] for r in [res1, res2]]
        assert True in successes
        assert False in successes
        logger.info(f"Double booking prevention locked out the second attempt correctly. Res1: {res1[0]}, Res2: {res2[0]}")

        # 6. Test Cancellation
        logger.info("\n--- Test Case 6: Cancellation ---")
        # Create event to cancel
        ev_to_cancel = calendar_service.create_event(
            title="Cancel Me",
            start=TimezoneService.normalize_to_utc("2026-06-11T12:00:00"),
            end=TimezoneService.normalize_to_utc("2026-06-11T12:30:00"),
            email="cancel@example.com",
            description="Topic"
        )
        assert calendar_service.cancel_event(ev_to_cancel["id"]) is True
        # Verify it is deleted
        events = calendar_service._read_mock_events()
        assert not any(ev["id"] == ev_to_cancel["id"] for ev in events)
        logger.info("Cancellation executed and verified successfully.")

        # 7. Test Rescheduling
        logger.info("\n--- Test Case 7: Rescheduling ---")
        ev_to_resched = calendar_service.create_event(
            title="Reschedule Me",
            start=TimezoneService.normalize_to_utc("2026-06-12T14:00:00"),
            end=TimezoneService.normalize_to_utc("2026-06-12T14:30:00"),
            email="resched@example.com",
            description="Topic"
        )
        
        new_start = TimezoneService.normalize_to_utc("2026-06-12T16:00:00")
        new_end = new_start + datetime.timedelta(minutes=30)
        
        updated = calendar_service.reschedule_event(ev_to_resched["id"], new_start, new_end)
        assert updated["start"] == new_start.isoformat()
        
        events = calendar_service._read_mock_events()
        found_ev = next(ev for ev in events if ev["id"] == ev_to_resched["id"])
        assert found_ev["start"] == new_start.isoformat()
        logger.info("Rescheduling verified successfully.")

        # 8. Test Chat Integration Multi-Turn Routing
        logger.info("\n--- Test Case 8: Multi-Turn Conversation Booking Routing ---")
        qa_engine = QAEngine()
        
        # Turn 1: Start Flow
        response = await qa_engine.answer_question("I want to schedule an interview")
        logger.info(f"Turn 1 response: '{response.answer}'")
        assert "timezone" in response.answer.lower()
        assert response.session_id is not None
        assert response.booking_context["step"] == "ask_timezone"
        
        session_id = response.session_id
        booking_ctx = response.booking_context
        
        # Turn 2: Provide Timezone
        response = await qa_engine.answer_question(
            question="IST",
            session_id=session_id,
            booking_context=booking_ctx
        )
        logger.info(f"Turn 2 response: '{response.answer}'")
        assert "email" in response.answer.lower()
        assert response.booking_context["step"] == "ask_email"
        
        booking_ctx = response.booking_context

        # Turn 3: Provide Email
        response = await qa_engine.answer_question(
            question="candidate@test.com",
            session_id=session_id,
            booking_context=booking_ctx
        )
        logger.info(f"Turn 3 response: '{response.answer}'")
        assert "discuss" in response.answer.lower() or "topic" in response.answer.lower()
        assert response.booking_context["step"] == "ask_topic"
        
        booking_ctx = response.booking_context

        # Turn 4: Provide Topic
        response = await qa_engine.answer_question(
            question="AI Persona Engineering",
            session_id=session_id,
            booking_context=booking_ctx
        )
        logger.info(f"Turn 4 response: '{response.answer}'")
        assert "available timeslots" in response.answer.lower()
        assert len(response.booking_context["available_slots"]) > 0
        assert response.booking_context["step"] == "recommend_slots"
        
        booking_ctx = response.booking_context

        # Turn 5: Choose Slot 1
        response = await qa_engine.answer_question(
            question="1",
            session_id=session_id,
            booking_context=booking_ctx
        )
        logger.info(f"Turn 5 response: '{response.answer}'")
        assert "successfully scheduled" in response.answer.lower()
        assert response.booking_context["step"] == "none"

        logger.info("\n=== ALL BOOKING & CALENDAR AGENT LAYER TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_booking_tests())
