from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.services.time_windows import participant_window_utc


def compute_slot(now_utc: datetime, frequency: str, start_t, end_t, scope: str, participant_tz: str, challenge_tz: str | None, custom_days: list[int] | None = None):
    """
    Compute current slot (anchor local date string), plus the UTC window.
    Returns: (slot_key: str, start_utc: datetime, end_utc: datetime) or None if outside window / weekend for 'weekdays' / custom days.
    """
    # Determine which tz governs the slot's anchor day
    tz_name = participant_tz if scope == "participant_local" else (challenge_tz or "UTC")
    local_now = now_utc.astimezone(ZoneInfo(tz_name))
    anchor = local_now.date()

    if frequency == "weekly":
        # Monday = 0
        anchor = anchor - timedelta(days=anchor.weekday())
    elif frequency == "weekdays":
        if anchor.weekday() >= 5:  # Sat=5, Sun=6
            return None
    elif frequency == "custom":
        # Check if today is one of the allowed custom days
        if custom_days is None or anchor.weekday() not in custom_days:
            return None

    start_utc, end_utc = participant_window_utc(anchor, start_t, end_t, scope, participant_tz, challenge_tz)

    if not (start_utc <= now_utc <= end_utc):
        return None

    slot_key = anchor.isoformat()
    return slot_key, start_utc, end_utc