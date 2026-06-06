import time
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException
from app.models.booking import (
    AvailabilityResponse, SlotItem, BookingCreateRequest, BookingCreateResponse,
    BookingCancelRequest, BookingRescheduleRequest
)
from app.services.booking_engine import AvailabilityEngine, SlotRecommendationService
from app.services.booking_orchestrator import BookingOrchestrator
from app.services.calendar_service import CalendarService
from app.services.observability import ObservabilityService
from app.core.logging import logger

router = APIRouter()
calendar_service = CalendarService()

@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(timezone: str = "IST", duration_minutes: int = 30):
    """Retrieves the top 5 available timeslots for interview bookings in candidate's timezone."""
    start_time = time.time()
    try:
        slots = AvailabilityEngine.get_available_slots(
            target_tz_name=timezone,
            duration_minutes=duration_minutes,
            calendar_service=calendar_service
        )
        ranked = SlotRecommendationService.rank_slots(slots, target_tz_name=timezone)
        
        latency = (time.time() - start_time) * 1000
        ObservabilityService.log_booking_event("get_availability", "success", latency, f"slots_found={len(ranked)}")
        
        return AvailabilityResponse(
            timezone=timezone,
            slots=[SlotItem(display=s["display"], utc=s["utc"]) for s in ranked]
        )
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        ObservabilityService.log_booking_event("get_availability", "failure", latency, str(e))
        logger.error(f"Error fetching availability: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch availability: {str(e)}")

@router.post("/create", response_model=BookingCreateResponse)
async def create_booking(request: BookingCreateRequest):
    """Directly schedules a calendar booking, preventing double-bookings with locks."""
    start_time = time.time()
    try:
        success, details_or_error = await BookingOrchestrator._lock_and_book_slot(
            start_time_str=request.start_time,
            duration_minutes=request.duration_minutes,
            email=request.attendee_email,
            topic=request.interest_topic or "Interview",
            timezone=request.timezone,
            calendar_service=calendar_service
        )
        
        latency = (time.time() - start_time) * 1000
        if success:
            ObservabilityService.log_booking_event(
                "create_booking", "success", latency, 
                f"event_id={details_or_error['id']}, email={request.attendee_email}"
            )
            return BookingCreateResponse(
                confirmation_id=details_or_error["id"],
                title=details_or_error["title"],
                start_time=details_or_error["start_time"],
                end_time=details_or_error["end_time"],
                timezone=request.timezone,
                attendee_email=details_or_error["attendee_email"],
                description=details_or_error["description"],
                html_link=f"https://calendar.google.com/calendar/event?eid={details_or_error['id']}"
            )
        else:
            ObservabilityService.log_booking_event("create_booking", "conflict", latency, details_or_error)
            raise HTTPException(status_code=409, detail=details_or_error)
            
    except HTTPException as he:
        raise he
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        ObservabilityService.log_booking_event("create_booking", "failure", latency, str(e))
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create booking: {str(e)}")

@router.post("/cancel")
async def cancel_booking(request: BookingCancelRequest):
    """Cancels a scheduled interview event by ID."""
    start_time = time.time()
    try:
        # Search by email if event_id is blank, or use direct cancel_event
        success = False
        if request.event_id:
            success = calendar_service.cancel_event(request.event_id)
        elif request.attendee_email:
            success = BookingOrchestrator._execute_cancellation(request.attendee_email, calendar_service)

        latency = (time.time() - start_time) * 1000
        if success:
            ObservabilityService.log_booking_event("cancel_booking", "success", latency, f"event_id={request.event_id}")
            return {"status": "success", "message": "Booking successfully cancelled."}
        else:
            ObservabilityService.log_booking_event("cancel_booking", "not_found", latency, f"event_id={request.event_id}")
            raise HTTPException(status_code=404, detail="Booking event not found.")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        ObservabilityService.log_booking_event("cancel_booking", "failure", latency, str(e))
        logger.error(f"Error cancelling booking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel booking: {str(e)}")

@router.post("/reschedule")
async def reschedule_booking(request: BookingRescheduleRequest):
    """Reschedules an existing interview to a new available slot."""
    start_time = time.time()
    try:
        # Fetch existing event to retrieve email/topic
        email = None
        topic = "Interview"
        
        if not calendar_service.use_real_cal:
            events = calendar_service._read_mock_events()
            for ev in events:
                if ev["id"] == request.event_id:
                    email = ev["attendee_email"]
                    topic = ev.get("description", "").split("Discussion Topic:\n")[-1].split("\n")[0] if "Discussion Topic:\n" in ev.get("description", "") else "Interview"
                    break
        else:
            try:
                event = calendar_service.service.events().get(
                    calendarId=calendar_service.calendar_id, eventId=request.event_id
                ).execute()
                # Safely extract attendee email
                attendees = event.get("attendees") or []
                email = attendees[0].get("email") if attendees else ""
                topic = event.get("description", "").split("Discussion Topic:\n")[-1].split("\n")[0] if "Discussion Topic:\n" in event.get("description", "") else "Interview"
            except Exception as e:
                logger.error(f"Failed to fetch event for rescheduling details: {e}")

        if not email:
            raise HTTPException(status_code=404, detail="Original booking event not found.")

        success, details_or_error = await BookingOrchestrator._lock_and_reschedule_slot(
            event_id=request.event_id,
            new_start_time_str=request.new_start_time,
            duration_minutes=30,
            email=email,
            topic=topic,
            timezone=request.timezone,
            calendar_service=calendar_service
        )
        
        latency = (time.time() - start_time) * 1000
        if success:
            ObservabilityService.log_booking_event(
                "reschedule_booking", "success", latency, 
                f"event_id={request.event_id}, email={email}"
            )
            return {
                "status": "success",
                "message": "Booking successfully rescheduled.",
                "details": {
                    "confirmation_id": request.event_id,
                    "title": details_or_error["title"],
                    "start_time": details_or_error["start_time"],
                    "end_time": details_or_error["end_time"],
                    "timezone": request.timezone,
                    "attendee_email": email
                }
            }
        else:
            ObservabilityService.log_booking_event("reschedule_booking", "conflict", latency, details_or_error)
            raise HTTPException(status_code=409, detail=details_or_error)
            
    except HTTPException as he:
        raise he
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        ObservabilityService.log_booking_event("reschedule_booking", "failure", latency, str(e))
        logger.error(f"Error rescheduling booking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reschedule booking: {str(e)}")
