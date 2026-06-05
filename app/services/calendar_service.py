import os
import json
import uuid
import datetime
import threading
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from app.core.config import settings
from app.core.logging import logger

# Try imports, catch if not installed (though we installed them in .venv)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

class CalendarService:
    _lock = threading.Lock()

    def __init__(self):
        self.calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
        self.creds_json = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")
        self.use_real_cal = False
        self.service = None

        if GOOGLE_LIBS_AVAILABLE and self.creds_json:
            try:
                # Can be direct JSON string or a file path
                if self.creds_json.strip().startswith("{"):
                    info = json.loads(self.creds_json)
                    creds = service_account.Credentials.from_service_account_info(
                        info, scopes=["https://www.googleapis.com/auth/calendar"]
                    )
                else:
                    creds = service_account.Credentials.from_service_account_file(
                        self.creds_json, scopes=["https://www.googleapis.com/auth/calendar"]
                    )
                self.service = build("calendar", "v3", credentials=creds)
                self.use_real_cal = True
                logger.info("Successfully authenticated with Google Calendar API.")
            except Exception as e:
                logger.error(f"Google Calendar authentication failed: {e}. Falling back to sandbox mock mode.")

        if not self.use_real_cal:
            self.mock_file = Path(settings.DATA_DIR) / "mock_calendar.json"
            self.mock_file.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using mock calendar sandbox file at: {self.mock_file}")

    def _read_mock_events(self) -> List[Dict[str, Any]]:
        if not self.mock_file.exists():
            return []
        try:
            with open(self.mock_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading mock calendar: {e}")
            return []

    def _write_mock_events(self, events: List[Dict[str, Any]]):
        try:
            with open(self.mock_file, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing mock calendar: {e}")

    def get_busy_slots(self, start_time: datetime.datetime, end_time: datetime.datetime) -> List[Tuple[datetime.datetime, datetime.datetime]]:
        """Returns list of busy (start, end) time ranges in UTC."""
        # Ensure timezone-aware UTC
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=datetime.timezone.utc)

        if self.use_real_cal:
            try:
                body = {
                    "timeMin": start_time.isoformat(),
                    "timeMax": end_time.isoformat(),
                    "items": [{"id": self.calendar_id}]
                }
                query = self.service.freebusy().query(body=body).execute()
                busy_list = query.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
                
                results = []
                for b in busy_list:
                    b_start = datetime.datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
                    b_end = datetime.datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
                    results.append((b_start.astimezone(datetime.timezone.utc), b_end.astimezone(datetime.timezone.utc)))
                return results
            except Exception as e:
                logger.error(f"Google Calendar freebusy query failed: {e}. Defaulting to mock calendar.")
                # Fallthrough to mock if real calendar errors out

        # Mock Sandbox Calendar logic
        with self._lock:
            events = self._read_mock_events()
            busy = []
            for ev in events:
                ev_start = datetime.datetime.fromisoformat(ev["start"])
                ev_end = datetime.datetime.fromisoformat(ev["end"])
                
                # Check overlap with start_time and end_time
                if ev_end > start_time and ev_start < end_time:
                    busy.append((ev_start, ev_end))
            return sorted(busy, key=lambda x: x[0])

    def create_event(self, title: str, start: datetime.datetime, end: datetime.datetime, email: str, description: str) -> Dict[str, Any]:
        """Creates a calendar event and returns event details."""
        if start.tzinfo is None:
            start = start.replace(tzinfo=datetime.timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=datetime.timezone.utc)

        if self.use_real_cal:
            try:
                event_body = {
                    "summary": title,
                    "description": description,
                    "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                    "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                    "attendees": [{"email": email}]
                }
                created = self.service.events().insert(calendarId=self.calendar_id, body=event_body).execute()
                return {
                    "id": created["id"],
                    "summary": created.get("summary", title),
                    "description": created.get("description", description),
                    "start": created["start"]["dateTime"],
                    "end": created["end"]["dateTime"],
                    "attendee_email": email,
                    "html_link": created.get("htmlLink")
                }
            except Exception as e:
                logger.error(f"Google Calendar event creation failed: {e}. Using mock calendar backup.")

        # Mock Sandbox Calendar logic
        with self._lock:
            events = self._read_mock_events()
            event_id = f"mock_{uuid.uuid4().hex[:12]}"
            new_event = {
                "id": event_id,
                "summary": title,
                "description": description,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "attendee_email": email
            }
            events.append(new_event)
            self._write_mock_events(events)
            return {
                "id": event_id,
                "summary": title,
                "description": description,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "attendee_email": email,
                "html_link": f"https://calendar.google.com/calendar/event?eid={event_id}"
            }

    def cancel_event(self, event_id: str) -> bool:
        """Deletes a calendar event. Returns True if successful, False otherwise."""
        if self.use_real_cal:
            try:
                self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
                return True
            except Exception as e:
                logger.error(f"Google Calendar event deletion failed: {e}. Attempting mock calendar.")

        # Mock Sandbox Calendar logic
        with self._lock:
            events = self._read_mock_events()
            initial_len = len(events)
            events = [ev for ev in events if ev["id"] != event_id]
            if len(events) < initial_len:
                self._write_mock_events(events)
                return True
            return False

    def reschedule_event(self, event_id: str, new_start: datetime.datetime, new_end: datetime.datetime) -> Dict[str, Any]:
        """Reschedules an event to new times."""
        if new_start.tzinfo is None:
            new_start = new_start.replace(tzinfo=datetime.timezone.utc)
        if new_end.tzinfo is None:
            new_end = new_end.replace(tzinfo=datetime.timezone.utc)

        if self.use_real_cal:
            try:
                event = self.service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
                event["start"] = {"dateTime": new_start.isoformat(), "timeZone": "UTC"}
                event["end"] = {"dateTime": new_end.isoformat(), "timeZone": "UTC"}
                updated = self.service.events().update(calendarId=self.calendar_id, eventId=event_id, body=event).execute()
                return {
                    "id": updated["id"],
                    "summary": updated.get("summary"),
                    "description": updated.get("description"),
                    "start": updated["start"]["dateTime"],
                    "end": updated["end"]["dateTime"],
                    "attendee_email": updated.get("attendees", [{}])[0].get("email", ""),
                    "html_link": updated.get("htmlLink")
                }
            except Exception as e:
                logger.error(f"Google Calendar rescheduling failed: {e}. Attempting mock calendar.")

        # Mock Sandbox Calendar logic
        with self._lock:
            events = self._read_mock_events()
            for ev in events:
                if ev["id"] == event_id:
                    ev["start"] = new_start.isoformat()
                    ev["end"] = new_end.isoformat()
                    self._write_mock_events(events)
                    return {
                        "id": event_id,
                        "summary": ev["summary"],
                        "description": ev["description"],
                        "start": ev["start"],
                        "end": ev["end"],
                        "attendee_email": ev["attendee_email"],
                        "html_link": f"https://calendar.google.com/calendar/event?eid={event_id}"
                    }
            raise ValueError(f"Event with ID {event_id} not found in calendar.")
