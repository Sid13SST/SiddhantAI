import datetime
# pyrefly: ignore [missing-import]
import pytz
from typing import List, Dict, Any, Tuple, Optional
from app.services.timezone_service import TimezoneService
from app.services.calendar_service import CalendarService

class AvailabilityEngine:
    @classmethod
    def get_available_slots(
        cls,
        target_tz_name: str,
        duration_minutes: int = 30,
        date_range_days: int = 7,
        calendar_service: Optional[CalendarService] = None
    ) -> List[datetime.datetime]:
        """Scans the calendar for available slots respecting working hours (09:00-20:00 IST), busy times, and 15m buffers."""
        if calendar_service is None:
            calendar_service = CalendarService()

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        ist_tz = pytz.timezone("Asia/Kolkata")
        
        # Determine current date in IST to align slot generation days
        now_ist = now_utc.astimezone(ist_tz)
        today_ist = now_ist.date()

        # Query busy slots from calendar service
        scan_end_utc = now_utc + datetime.timedelta(days=date_range_days)
        busy_slots = calendar_service.get_busy_slots(now_utc, scan_end_utc)

        available_slots = []
        buffer_delta = datetime.timedelta(minutes=15)
        duration_delta = datetime.timedelta(minutes=duration_minutes)

        # Iterate over each day in the date range
        for i in range(date_range_days):
            current_date_ist = today_ist + datetime.timedelta(days=i)
            
            # Generate slots from 09:00 to 20:00 IST
            # Step by 30 minutes
            start_hour_ist = ist_tz.localize(datetime.datetime.combine(current_date_ist, datetime.time(9, 0)))
            end_hour_ist = ist_tz.localize(datetime.datetime.combine(current_date_ist, datetime.time(20, 0)))
            
            temp_start = start_hour_ist
            while temp_start + duration_delta <= end_hour_ist:
                slot_start_utc = temp_start.astimezone(datetime.timezone.utc)
                slot_end_utc = slot_start_utc + duration_delta

                # 1. Ignore past times
                if slot_start_utc <= now_utc:
                    temp_start += datetime.timedelta(minutes=30)
                    continue

                # 2. Check for overlaps with busy slots (including 15m buffer)
                has_overlap = False
                for busy_start, busy_end in busy_slots:
                    # Apply 15m buffer before and after busy events
                    buffered_busy_start = busy_start - buffer_delta
                    buffered_busy_end = busy_end + buffer_delta
                    
                    if slot_end_utc > buffered_busy_start and slot_start_utc < buffered_busy_end:
                        has_overlap = True
                        break

                if not has_overlap:
                    available_slots.append(slot_start_utc)

                temp_start += datetime.timedelta(minutes=30)

        return available_slots

class SlotRecommendationService:
    @classmethod
    def rank_slots(
        cls,
        available_slots: List[datetime.datetime],
        target_tz_name: str
    ) -> List[Dict[str, str]]:
        """Ranks available slots prioritizing timezone friendliness, standard interview windows, and earliest dates."""
        tz = TimezoneService.get_tz(target_tz_name)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        ranked_list = []
        for slot in available_slots:
            local_dt = slot.astimezone(tz)
            local_hour = local_dt.hour + (local_dt.minute / 60.0)
            
            # 1. User Timezone Friendliness Score
            # Prioritize standard business hours (8:00 AM - 6:00 PM) in the candidate's timezone
            if 8.0 <= local_hour < 18.0:
                tz_friendliness = 1.0
            elif (6.0 <= local_hour < 8.0) or (18.0 <= local_hour < 22.0):
                tz_friendliness = 0.5
            else:
                tz_friendliness = 0.0
                
            # 2. Consistent Interview Windows Score
            # Boost slots that fall in standard peak interview windows (10:00-12:00 or 14:00-17:00) local target time
            if (10.0 <= local_hour <= 12.0) or (14.0 <= local_hour <= 17.0):
                is_interview_window = 1.0
            else:
                is_interview_window = 0.0

            # 3. Proximity / Days from now penalty
            days_from_now = (slot - now_utc).total_seconds() / (24 * 3600)
            
            # Combine scores (higher is better)
            priority_score = (tz_friendliness * 5.0) + (is_interview_window * 3.0) - (days_from_now * 0.5)
            
            ranked_list.append((slot, priority_score))

        # Sort descending by priority_score
        ranked_list.sort(key=lambda x: x[1], reverse=True)

        # Take top 5 and format
        top_slots = ranked_list[:5]
        
        results = []
        for slot, _ in top_slots:
            display_str = TimezoneService.format_friendly_time(slot, target_tz_name)
            results.append({
                "display": display_str,
                "utc": slot.strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            
        return results
