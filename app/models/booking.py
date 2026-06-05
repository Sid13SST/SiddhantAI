from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class SlotItem(BaseModel):
    display: str = Field(..., description="Human-friendly readable time representation, e.g. 'Tomorrow at 3:30 PM IST'")
    utc: str = Field(..., description="UTC ISO format string representation of slot start time")

class AvailabilityResponse(BaseModel):
    timezone: str = Field(..., description="The timezone requested for slot mapping")
    slots: List[SlotItem] = Field(default_factory=list, description="Available timeslots for interviews")

class BookingCreateRequest(BaseModel):
    start_time: str = Field(..., description="The chosen slot's start time in UTC format (ISO 8601)")
    timezone: str = Field("IST", description="The timezone of the candidate, e.g. 'IST', 'PST', etc.")
    attendee_email: str = Field(..., description="Candidate email address")
    duration_minutes: int = Field(30, description="Duration of the interview in minutes")
    interest_topic: Optional[str] = Field(None, description="Discussion interest topic, e.g. 'AI Engineering Internship'")

class BookingCreateResponse(BaseModel):
    confirmation_id: str = Field(..., description="Unique booking ID or calendar event ID")
    title: str = Field(..., description="Title of the interview event")
    start_time: str = Field(..., description="Start time formatted for user")
    end_time: str = Field(..., description="End time formatted for user")
    timezone: str = Field(..., description="Timezone applied to the booking")
    attendee_email: str = Field(..., description="Candidate email address")
    description: str = Field(..., description="Event description containing discussion topic metadata")
    html_link: Optional[str] = Field(None, description="Google Calendar HTML booking event link")

class BookingCancelRequest(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to cancel")
    attendee_email: Optional[str] = Field(None, description="Optional email of attendee to verify ownership")

class BookingRescheduleRequest(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to reschedule")
    new_start_time: str = Field(..., description="The new chosen slot's start time in UTC ISO 8601 format")
    timezone: str = Field("IST", description="The timezone context for reschedule confirmation")
