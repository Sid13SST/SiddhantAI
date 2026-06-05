import datetime
# pyrefly: ignore [missing-import]
import pytz
from typing import Dict, Optional

class TimezoneService:
    # Supported timezone abbreviation mappings to standard Olson IDs
    TZ_MAP: Dict[str, str] = {
        "IST": "Asia/Kolkata",
        "UTC": "UTC",
        "EST": "America/New_York",
        "PST": "America/Los_Angeles",
        "GMT": "Europe/London",
        "PHT": "Asia/Manila", # Just in case
    }

    @classmethod
    def get_tz(cls, tz_name: str) -> pytz.BaseTzInfo:
        """Resolves a timezone name/abbreviation to a pytz timezone object."""
        normalized = tz_name.strip().upper()
        olson_name = cls.TZ_MAP.get(normalized, normalized)
        try:
            return pytz.timezone(olson_name)
        except Exception:
            return pytz.UTC

    @classmethod
    def normalize_to_utc(cls, dt_str: str) -> datetime.datetime:
        """Parses an ISO 8601 string and returns a timezone-aware UTC datetime."""
        # Strip trailing Z and parse
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(dt_str)
        except ValueError:
            # Try parsing custom format if any
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        else:
            dt = dt.astimezone(pytz.UTC)
        return dt

    @classmethod
    def format_friendly_time(cls, utc_dt: datetime.datetime, target_tz_name: str) -> str:
        """Converts a UTC datetime to target timezone and formats as 'Tomorrow at 3:30 PM IST' etc."""
        tz = cls.get_tz(target_tz_name)
        local_dt = utc_dt.astimezone(tz)
        
        # Determine today/tomorrow in the local timezone perspective
        now_local = datetime.datetime.now(tz)
        today = now_local.date()
        tomorrow = today + datetime.timedelta(days=1)
        slot_date = local_dt.date()
        
        # Time format: e.g. "3:30 PM"
        time_str = local_dt.strftime("%I:%M %p").lstrip("0")
        tz_abbrev = target_tz_name.upper()

        if slot_date == today:
            return f"Today at {time_str} {tz_abbrev}"
        elif slot_date == tomorrow:
            return f"Tomorrow at {time_str} {tz_abbrev}"
        else:
            # e.g., "Monday, June 8 at 3:30 PM IST"
            day_str = local_dt.strftime("%A, %B %d")
            # Remove leading zero on day if any (e.g. June 08 -> June 8)
            day_str = day_str.replace(" 0", " ")
            return f"{day_str} at {time_str} {tz_abbrev}"
