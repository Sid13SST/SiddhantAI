import datetime
import re
import threading
from typing import Dict, Any, Tuple, Optional, List
from app.models.qa import QAResponse, EvidenceItem
from app.models.booking import SlotItem
from app.services.calendar_service import CalendarService
from app.services.timezone_service import TimezoneService
from app.services.booking_engine import AvailabilityEngine, SlotRecommendationService
from app.core.logging import logger

# Global in-memory locks for double-booking prevention
ACTIVE_LOCKS = set()
LOCKS_MUTEX = threading.Lock()

# Global backend session cache as a fallback for stateless APIs
SESSION_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_MUTEX = threading.Lock()

class BookingOrchestrator:
    SESSION_CACHE = SESSION_CACHE
    CACHE_MUTEX = CACHE_MUTEX

    @classmethod
    def get_or_create_session(cls, session_id: Optional[str], client_context: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Retrieves or creates session context, favoring client-side state for statelessness."""
        if not session_id:
            import uuid
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        # If client passed context, adopt it (this satisfies Next.js frontend state ownership)
        if client_context:
            with CACHE_MUTEX:
                SESSION_CACHE[session_id] = client_context
            return session_id, client_context

        # Fallback to backend cache
        with CACHE_MUTEX:
            if session_id not in SESSION_CACHE:
                SESSION_CACHE[session_id] = {
                    "step": "none",
                    "action": "none",
                    "timezone": "IST",
                    "duration": 30,
                    "email": None,
                    "topic": None,
                    "event_id": None,
                    "available_slots": []
                }
            return session_id, SESSION_CACHE[session_id]

    @classmethod
    def update_session(cls, session_id: str, context: Dict[str, Any]):
        with CACHE_MUTEX:
            SESSION_CACHE[session_id] = context

    @classmethod
    def validate_email(cls, email: str) -> bool:
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return bool(re.match(pattern, email))

    @classmethod
    async def process_booking_message(cls, question: str, session_id: str, context: Dict[str, Any], intent: str) -> QAResponse:
        """Processes scheduling conversational turns, advancing the state machine."""
        q_clean = question.strip()
        step = context.get("step", "none")
        action = context.get("action", "none")
        calendar_service = CalendarService()

        logger.info(f"BookingOrchestrator: session={session_id}, action={action}, step={step}, input='{q_clean}', intent={intent}")

        # Start of a new flow or explicit intent override
        if intent == "cancellation_request" and action != "cancellation":
            context["action"] = "cancellation"
            context["step"] = "ask_cancellation_email"
            cls.update_session(session_id, context)
            return QAResponse(
                answer="I can certainly help you cancel your interview with Siddhant. Could you please provide the candidate email address used for the booking?",
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )
            
        elif intent == "reschedule_request" and action != "reschedule":
            context["action"] = "reschedule"
            context["step"] = "ask_reschedule_email"
            cls.update_session(session_id, context)
            return QAResponse(
                answer="Sure, I can help you reschedule your interview. To locate your current booking, what is the candidate email address associated with it?",
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )

        elif (intent in ["booking_request", "availability_check"]) and action not in ["booking", "reschedule"] and step == "none":
            context["action"] = "booking"
            context["step"] = "ask_timezone"
            cls.update_session(session_id, context)
            return QAResponse(
                answer="I'd be glad to help you schedule an interview with Siddhant! To display the correct available times, could you please tell me your timezone (e.g. IST, EST, PST, GMT, UTC)?",
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )

        # STATE MACHINE PROCESSING
        
        # 1. Ask Timezone
        if step == "ask_timezone":
            tz_input = q_clean.upper().replace(" ", "")
            # Try to resolve timezone
            tz_resolved = TimezoneService.TZ_MAP.get(tz_input)
            if not tz_resolved:
                # If they entered something like "Kolkata" or "New York"
                for abbrev, olson in TimezoneService.TZ_MAP.items():
                    if tz_input in olson.upper() or tz_input in abbrev:
                        tz_input = abbrev
                        break
                else:
                    return QAResponse(
                        answer="Sorry, I didn't recognize that timezone. Please provide a standard abbreviation like IST, EST, PST, GMT, or UTC.",
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )
            
            context["timezone"] = tz_input
            context["step"] = "ask_email"
            cls.update_session(session_id, context)
            return QAResponse(
                answer=f"Got it, {tz_input}. Next, what is your email address so I can send the calendar invitation?",
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )

        # 2. Ask Email (Used for booking, cancellation, and rescheduling lookups)
        elif step in ["ask_email", "ask_cancellation_email", "ask_reschedule_email"]:
            # Extract email using regex
            emails_found = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", q_clean)
            if not emails_found:
                return QAResponse(
                    answer="That email address doesn't seem valid. Please enter a correct email (e.g. candidate@domain.com).",
                    confidence=1.0,
                    session_id=session_id,
                    booking_context=context
                )
            
            email = emails_found[0]
            context["email"] = email

            if step == "ask_cancellation_email":
                # Handle cancellation lookup and execution
                success = cls._execute_cancellation(email, calendar_service)
                if success:
                    context["step"] = "none"
                    context["action"] = "none"
                    context["last_cancellation_completed"] = True
                    cls.update_session(session_id, context)
                    return QAResponse(
                        answer=f"Your interview with Siddhant associated with {email} has been successfully cancelled. A calendar notification has been sent.",
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )
                else:
                    return QAResponse(
                        answer=f"I couldn't find any scheduled interviews under the email address: {email}. Please double check the email or type 'cancel' to abort.",
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )
                    
            elif step == "ask_reschedule_email":
                # Find event to reschedule
                event = cls._find_event_by_email(email, calendar_service)
                if not event:
                    return QAResponse(
                        answer=f"I couldn't find any scheduled interviews under the email address: {email}. Please check the email or type 'cancel' to start over.",
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )
                
                context["event_id"] = event["id"]
                context["topic"] = event.get("description", "").split("Discussion Topic:\n")[-1].split("\n")[0] if "Discussion Topic:\n" in event.get("description", "") else "Interview"
                # Switch to recommending slots for rescheduling
                context["step"] = "reschedule_recommend_slots"
                # Generate recommendations
                tz = context.get("timezone", "IST")
                slots = AvailabilityEngine.get_available_slots(target_tz_name=tz, calendar_service=calendar_service)
                ranked = SlotRecommendationService.rank_slots(slots, target_tz_name=tz)
                context["available_slots"] = ranked
                cls.update_session(session_id, context)
                
                slots_text = "\n".join([f"{idx+1}. {s['display']}" for idx, s in enumerate(ranked)])
                return QAResponse(
                    answer=(
                        f"I found your current booking! Let's choose a new time. Here are the top 5 available timeslots in your timezone ({tz}):\n\n"
                        f"{slots_text}\n\n"
                        "Which slot works best? Please reply with the slot number (1-5)."
                    ),
                    confidence=1.0,
                    session_id=session_id,
                    booking_context=context
                )

            # Booking flow: proceed to interest capture
            context["step"] = "ask_topic"
            cls.update_session(session_id, context)
            return QAResponse(
                answer="Thank you. What would you like to discuss during the interview? (e.g., AI Engineering Internship, Backend Role, General Chat)",
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )

        # 3. Ask Topic (Interview Context Capture)
        elif step == "ask_topic":
            context["topic"] = q_clean
            context["step"] = "recommend_slots"
            
            # Fetch and rank slots
            tz = context.get("timezone", "IST")
            slots = AvailabilityEngine.get_available_slots(target_tz_name=tz, calendar_service=calendar_service)
            ranked = SlotRecommendationService.rank_slots(slots, target_tz_name=tz)
            context["available_slots"] = ranked
            cls.update_session(session_id, context)

            slots_text = "\n".join([f"{idx+1}. {s['display']}" for idx, s in enumerate(ranked)])
            return QAResponse(
                answer=(
                    f"Got it, we will discuss '{q_clean}'. Here are the top 5 available timeslots for Siddhant in your timezone ({tz}):\n\n"
                    f"{slots_text}\n\n"
                    "Which slot works best for you? Please reply with the slot number (1-5) or type the slot date."
                ),
                confidence=1.0,
                session_id=session_id,
                booking_context=context
            )

        # 4. Slot Selection (Booking slot or Reschedule slot)
        elif step in ["recommend_slots", "reschedule_recommend_slots"]:
            # Parse choice (either index 1-5 or matches text)
            chosen_slot = cls._parse_slot_choice(q_clean, context.get("available_slots", []))
            if not chosen_slot:
                return QAResponse(
                    answer="I didn't quite get that. Please reply with a number from 1 to 5 to select your slot.",
                    confidence=1.0,
                    session_id=session_id,
                    booking_context=context
                )
            
            slot_utc_str = chosen_slot["utc"]
            slot_display = chosen_slot["display"]
            
            # 5. Lock and Execute Creation/Rescheduling (Double Booking Prevention)
            if step == "recommend_slots":
                success, details_or_error = await cls._lock_and_book_slot(
                    start_time_str=slot_utc_str,
                    duration_minutes=context.get("duration", 30),
                    email=context["email"],
                    topic=context["topic"],
                    timezone=context["timezone"],
                    calendar_service=calendar_service
                )
                
                if success:
                    context["step"] = "none"
                    context["action"] = "none"
                    context["last_booking_created"] = True
                    context["last_booking_id"] = details_or_error["id"]
                    cls.update_session(session_id, context)
                    
                    confirm_text = (
                        f"Awesome! Your interview with Siddhant has been successfully scheduled.\n\n"
                        f"**Confirmation Details:**\n"
                        f"- **Title:** {details_or_error['title']}\n"
                        f"- **Time:** {details_or_error['start_time']}\n"
                        f"- **Candidate Email:** {details_or_error['attendee_email']}\n"
                        f"- **Topic:** {context.get('topic')}\n\n"
                        f"I have sent a Google Calendar invitation to {details_or_error['attendee_email']}."
                    )
                    return QAResponse(
                        answer=confirm_text,
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context,
                        citations=["Google Calendar Booking Agent"],
                        sources=[EvidenceItem(source="Booking Agent", snippet=confirm_text)]
                    )
                else:
                    # Slot conflict occurred! Regenerate recommendation
                    logger.warning(f"Slot conflict triggered for {slot_utc_str}: {details_or_error}")
                    tz = context.get("timezone", "IST")
                    slots = AvailabilityEngine.get_available_slots(target_tz_name=tz, calendar_service=calendar_service)
                    ranked = SlotRecommendationService.rank_slots(slots, target_tz_name=tz)
                    context["available_slots"] = ranked
                    cls.update_session(session_id, context)
                    
                    slots_text = "\n".join([f"{idx+1}. {s['display']}" for idx, s in enumerate(ranked)])
                    return QAResponse(
                        answer=(
                            "Apologies, that slot was just filled by someone else! Let's choose another time. "
                            f"Here are the fresh available timeslots:\n\n{slots_text}\n\n"
                            "Which slot works best? Please reply with a slot number (1-5)."
                        ),
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )
            else:
                # Rescheduling execution
                success, details_or_error = await cls._lock_and_reschedule_slot(
                    event_id=context["event_id"],
                    new_start_time_str=slot_utc_str,
                    duration_minutes=context.get("duration", 30),
                    email=context["email"],
                    topic=context.get("topic", "Interview"),
                    timezone=context["timezone"],
                    calendar_service=calendar_service
                )
                
                if success:
                    context["step"] = "none"
                    context["action"] = "none"
                    context["last_booking_created"] = True
                    context["last_booking_id"] = details_or_error["id"]
                    cls.update_session(session_id, context)
                    
                    confirm_text = (
                        f"Great! Your interview with Siddhant has been successfully rescheduled.\n\n"
                        f"**New Details:**\n"
                        f"- **Time:** {details_or_error['start_time']}\n"
                        f"- **Candidate Email:** {details_or_error['attendee_email']}\n"
                        f"- **Topic:** {context.get('topic')}\n\n"
                        f"Your Google Calendar invite has been updated."
                    )
                    return QAResponse(
                        answer=confirm_text,
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context,
                        citations=["Google Calendar Booking Agent"],
                        sources=[EvidenceItem(source="Booking Agent", snippet=confirm_text)]
                    )
                else:
                    # Slot conflict occurred! Regenerate
                    logger.warning(f"Slot conflict triggered for reschedule {slot_utc_str}: {details_or_error}")
                    tz = context.get("timezone", "IST")
                    slots = AvailabilityEngine.get_available_slots(target_tz_name=tz, calendar_service=calendar_service)
                    ranked = SlotRecommendationService.rank_slots(slots, target_tz_name=tz)
                    context["available_slots"] = ranked
                    cls.update_session(session_id, context)
                    
                    slots_text = "\n".join([f"{idx+1}. {s['display']}" for idx, s in enumerate(ranked)])
                    return QAResponse(
                        answer=(
                            "Apologies, that slot was just filled by someone else! Let's choose another time. "
                            f"Here are the fresh available timeslots:\n\n{slots_text}\n\n"
                            "Which slot works best? Please reply with a slot number (1-5)."
                        ),
                        confidence=1.0,
                        session_id=session_id,
                        booking_context=context
                    )

        # Fallback safety response
        return QAResponse(
            answer="I am here to help you with booking. What timezone are you in?",
            confidence=1.0,
            session_id=session_id,
            booking_context=context
        )

    @classmethod
    def _parse_slot_choice(cls, text: str, available_slots: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Parses choice from index (1-5) or text match."""
        if not available_slots:
            return None
            
        m = re.search(r"\b([1-5])\b", text)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(available_slots):
                return available_slots[idx]

        # String match fallback
        for s in available_slots:
            if s["display"].lower() in text.lower():
                return s
        return None

    @classmethod
    def _execute_cancellation(cls, email: str, calendar_service: CalendarService) -> bool:
        """Finds and deletes the event for this attendee email."""
        event = cls._find_event_by_email(email, calendar_service)
        if event:
            return calendar_service.cancel_event(event["id"])
        return False

    @classmethod
    def _find_event_by_email(cls, email: str, calendar_service: CalendarService) -> Optional[Dict[str, Any]]:
        """Looks for an event in the mock calendar containing attendee email."""
        now = datetime.datetime.now(datetime.timezone.utc)
        future_limit = now + datetime.timedelta(days=30)
        
        # Read from mock calendar directly to find by email
        if not calendar_service.use_real_cal:
            events = calendar_service._read_mock_events()
            for ev in events:
                if ev.get("attendee_email") == email:
                    return ev
            return None
            
        # Real Calendar API search
        try:
            events_result = calendar_service.service.events().list(
                calendarId=calendar_service.calendar_id,
                timeMin=now.isoformat(),
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            for event in events_result.get("items", []):
                for att in event.get("attendees", []):
                    if att.get("email") == email:
                        return event
        except Exception as e:
            logger.error(f"Failed to find event by email: {e}")
        return None

    @classmethod
    async def _lock_and_book_slot(
        cls,
        start_time_str: str,
        duration_minutes: int,
        email: str,
        topic: str,
        timezone: str,
        calendar_service: CalendarService
    ) -> Tuple[bool, Any]:
        """Locks the slot, re-checks availability, and creates the Google Calendar event."""
        start_utc = TimezoneService.normalize_to_utc(start_time_str)
        end_utc = start_utc + datetime.timedelta(minutes=duration_minutes)

        # 1. Acquire global atomic lock for this specific slot time
        with LOCKS_MUTEX:
            if start_time_str in ACTIVE_LOCKS:
                return False, "Slot is currently being booked by another process."
            ACTIVE_LOCKS.add(start_time_str)

        try:
            # 2. Re-check busy slots from calendar service
            busy_slots = calendar_service.get_busy_slots(start_utc, end_utc)
            buffer_delta = datetime.timedelta(minutes=15)
            
            for b_start, b_end in busy_slots:
                # Apply buffer check
                if end_utc > (b_start - buffer_delta) and start_utc < (b_end + buffer_delta):
                    return False, "Slot has already been booked."

            # 3. Create Event with Professional Metadata
            title = f"Scaler Interview - Siddhant"
            description = (
                f"Booked Through:\nSiddhant's AI Representative\n\n"
                f"Candidate Email:\n{email}\n\n"
                f"Discussion Topic:\n{topic}\n\n"
                f"Created:\n{datetime.datetime.now(datetime.timezone.utc).isoformat()}Z"
            )
            
            event_details = calendar_service.create_event(
                title=title,
                start=start_utc,
                end=end_utc,
                email=email,
                description=description
            )
            
            # Format times for confirmation
            friendly_start = TimezoneService.format_friendly_time(start_utc, timezone)
            friendly_end = TimezoneService.format_friendly_time(end_utc, timezone)
            
            return True, {
                "id": event_details["id"],
                "title": title,
                "start_time": friendly_start,
                "end_time": friendly_end,
                "attendee_email": email,
                "description": description
            }
            
        finally:
            with LOCKS_MUTEX:
                ACTIVE_LOCKS.discard(start_time_str)

    @classmethod
    async def _lock_and_reschedule_slot(
        cls,
        event_id: str,
        new_start_time_str: str,
        duration_minutes: int,
        email: str,
        topic: str,
        timezone: str,
        calendar_service: CalendarService
    ) -> Tuple[bool, Any]:
        """Locks slot, re-checks, and reschedules event."""
        new_start_utc = TimezoneService.normalize_to_utc(new_start_time_str)
        new_end_utc = new_start_utc + datetime.timedelta(minutes=duration_minutes)

        # 1. Lock the slot
        with LOCKS_MUTEX:
            if new_start_time_str in ACTIVE_LOCKS:
                return False, "Slot is currently locked."
            ACTIVE_LOCKS.add(new_start_time_str)

        try:
            # 2. Re-check busy slots (excluding the current event_id if possible)
            busy_slots = calendar_service.get_busy_slots(new_start_utc, new_end_utc)
            
            # Filter out the slot we are moving (so it doesn't conflict with itself)
            if not calendar_service.use_real_cal:
                # For mock calendar, remove the existing event from busy slot verification
                events = calendar_service._read_mock_events()
                busy_slots = []
                for ev in events:
                    if ev["id"] != event_id:
                        ev_start = datetime.datetime.fromisoformat(ev["start"])
                        ev_end = datetime.datetime.fromisoformat(ev["end"])
                        if ev_end > new_start_utc and ev_start < new_end_utc:
                            busy_slots.append((ev_start, ev_end))

            buffer_delta = datetime.timedelta(minutes=15)
            for b_start, b_end in busy_slots:
                if new_end_utc > (b_start - buffer_delta) and new_start_utc < (b_end + buffer_delta):
                    return False, "Slot has already been booked."

            # 3. Execute reschedule
            rescheduled = calendar_service.reschedule_event(event_id, new_start_utc, new_end_utc)
            
            friendly_start = TimezoneService.format_friendly_time(new_start_utc, timezone)
            friendly_end = TimezoneService.format_friendly_time(new_end_utc, timezone)
            
            return True, {
                "id": event_id,
                "title": rescheduled.get("summary", "Scaler Interview - Siddhant"),
                "start_time": friendly_start,
                "end_time": friendly_end,
                "attendee_email": email,
                "description": rescheduled.get("description", "")
            }
            
        finally:
            with LOCKS_MUTEX:
                ACTIVE_LOCKS.discard(new_start_time_str)
