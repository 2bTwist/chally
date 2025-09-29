from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo


def local_window_to_utc(d: date, start_local: time, end_local: time, tz_name: str) -> tuple[datetime, datetime]:
    """
    Convert a local wall-clock window (start->end) on date `d` in timezone `tz_name`
    to UTC datetimes. Supports overnight windows (end <= start).
    
    DST rules:
      - If a local time does not exist (spring forward), start/end is shifted to the next valid instant.
      - If a time is ambiguous (fall back), the full repeated hour is considered in-window (choose first fold).
      
    Args:
        d: The local date for the window
        start_local: Start time (wall clock)
        end_local: End time (wall clock) 
        tz_name: IANA timezone name (e.g., "America/New_York")
        
    Returns:
        Tuple of (start_utc, end_utc) datetime objects
        
    Examples:
        >>> from datetime import date, time
        >>> d = date(2025, 1, 10)  # EST = UTC-5
        >>> start, end = local_window_to_utc(d, time(6, 0), time(23, 0), "America/New_York")
        >>> start.hour, end.hour
        (11, 4)  # 6 AM EST = 11 AM UTC, 11 PM EST = 4 AM UTC next day
    """
    tz = ZoneInfo(tz_name)

    def _aware(d: date, t: time) -> datetime:
        # Pick fold=0 by default; callers can refine later if needed.
        t = t.replace(fold=0) if hasattr(t, "fold") else t
        # Construct local aware datetime; zoneinfo may allow "nonexistent" nominal times;
        # if a later conversion detects order inversion, we'll normalize below.
        return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, t.microsecond, tzinfo=tz)

    start_dt_local = _aware(d, start_local)
    end_dt_local = _aware(d, end_local)
    
    # Handle overnight windows (e.g., 22:00-02:00)
    if end_local <= start_local:
        end_dt_local += timedelta(days=1)

    # Normalize possible DST gaps by ensuring monotonicity in UTC
    start_utc = start_dt_local.astimezone(dt_tz.utc)
    end_utc = end_dt_local.astimezone(dt_tz.utc)
    
    if end_utc <= start_utc:
        # Extremely rare path; nudge end by 1 hour to skip a DST gap
        end_utc += timedelta(hours=1)
        
    return start_utc, end_utc


def participant_window_utc(
    d: date, 
    start: time, 
    end: time, 
    scope: str, 
    participant_tz: str, 
    challenge_tz: str | None
) -> tuple[datetime, datetime]:
    """
    Get UTC window for a participant on a specific date, respecting the scope setting.
    
    Args:
        d: The date to compute the window for
        start: Start time from rules (wall clock)
        end: End time from rules (wall clock)
        scope: Either "participant_local" or "challenge_tz"
        participant_tz: Participant's IANA timezone
        challenge_tz: Challenge's IANA timezone (optional)
        
    Returns:
        Tuple of (start_utc, end_utc) datetime objects
        
    Examples:
        >>> from datetime import date, time
        >>> d = date(2025, 1, 10)
        >>> # Participant in PST sees 6-23 in their local time
        >>> start, end = participant_window_utc(d, time(6), time(23), "participant_local", "America/Los_Angeles", None)
        >>> start.hour, end.hour  
        (14, 7)  # 6 AM PST = 2 PM UTC, 11 PM PST = 7 AM UTC next day
        
        >>> # Challenge timezone mode - everyone uses challenge's timezone
        >>> start, end = participant_window_utc(d, time(6), time(23), "challenge_tz", "America/Los_Angeles", "America/New_York")
        >>> start.hour, end.hour
        (11, 4)  # Uses EST, not PST
    """
    tz_name = participant_tz if scope == "participant_local" else (challenge_tz or "UTC")
    return local_window_to_utc(d, start, end, tz_name)