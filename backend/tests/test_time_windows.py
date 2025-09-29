from __future__ import annotations
from datetime import date, time, timezone
from app.services.time_windows import local_window_to_utc, participant_window_utc
from zoneinfo import ZoneInfo
import pytest


def _fmt(dt): 
    """Helper to format datetime for readability in tests"""
    return dt.isoformat()


def test_est_and_pst_same_wall_clock_different_utc():
    """Test that same wall-clock hours result in different UTC times for different timezones"""
    d = date(2025, 1, 10)  # Standard time (EST/PST, not EDT/PDT)
    start = time(6, 0, 0)
    end = time(23, 0, 0)

    s_utc_ny, e_utc_ny = local_window_to_utc(d, start, end, "America/New_York")
    s_utc_la, e_utc_la = local_window_to_utc(d, start, end, "America/Los_Angeles")

    # EST = UTC-5 -> 06:00 local = 11:00Z; 23:00 local = 04:00Z next day
    assert s_utc_ny.hour == 11 and s_utc_ny.tzinfo == timezone.utc
    assert e_utc_ny.hour == 4 and (e_utc_ny - s_utc_ny).total_seconds() == 17*3600

    # PST = UTC-8 -> 06:00 local = 14:00Z; 23:00 local = 07:00Z next day
    assert s_utc_la.hour == 14 and s_utc_la.tzinfo == timezone.utc
    assert e_utc_la.hour == 7 and (e_utc_la - s_utc_la).total_seconds() == 17*3600


def test_dst_spring_forward_ny():
    """Test DST spring forward - when clocks jump ahead"""
    # US DST starts 2025-03-09; 02:00 -> 03:00 skip. Our 06:00-23:00 remains valid.
    d = date(2025, 3, 9)
    s_utc, e_utc = local_window_to_utc(d, time(6, 0), time(23, 0), "America/New_York")
    
    # EDT = UTC-4 (during DST)
    assert s_utc.hour == 10 and e_utc.hour == 3
    # Window should still be 17 hours
    assert (e_utc - s_utc).total_seconds() == 17*3600


def test_dst_fall_back_ny():
    """Test DST fall back - when clocks fall back and hour repeats"""
    # US DST ends 2025-11-02; 02:00 -> 01:00 repeat. Our 06:00-23:00 spans the repeat.
    d = date(2025, 11, 2)
    s_utc, e_utc = local_window_to_utc(d, time(6, 0), time(23, 0), "America/New_York")
    
    # Should handle the repeated hour gracefully
    assert s_utc.tzinfo == timezone.utc and e_utc.tzinfo == timezone.utc
    # Window might be 18 hours due to the repeated hour
    duration_hours = (e_utc - s_utc).total_seconds() / 3600
    assert 17 <= duration_hours <= 18  # Allow for DST complexity


def test_overnight_window():
    """Test overnight windows that cross midnight"""
    d = date(2025, 1, 10)
    s_utc, e_utc = local_window_to_utc(d, time(22, 0), time(2, 0), "America/Los_Angeles")
    
    # Overnight window should be ~4 hours (22:00 to 02:00 next day)
    assert (e_utc - s_utc).total_seconds() == 4*3600
    
    # Start should be 22:00 PST = 06:00 UTC next day, end should be 02:00 PST = 10:00 UTC next day
    assert s_utc.hour == 6 and e_utc.hour == 10


def test_edge_case_midnight_window():
    """Test exact midnight boundaries"""
    d = date(2025, 1, 10)
    s_utc, e_utc = local_window_to_utc(d, time(0, 0), time(23, 59, 59), "UTC")
    
    # Should be almost a full day
    duration_seconds = (e_utc - s_utc).total_seconds()
    assert duration_seconds == 23*3600 + 59*60 + 59  # 23:59:59


def test_participant_window_utc_participant_local():
    """Test participant_window_utc with participant_local scope"""
    d = date(2025, 1, 10)
    
    # Participant in PST sees 6-23 in their local time
    start, end = participant_window_utc(
        d, time(6), time(23), "participant_local", "America/Los_Angeles", None
    )
    
    # 6 AM PST = 2 PM UTC, 11 PM PST = 7 AM UTC next day
    assert start.hour == 14 and end.hour == 7


def test_participant_window_utc_challenge_tz():
    """Test participant_window_utc with challenge_tz scope"""
    d = date(2025, 1, 10)
    
    # Challenge timezone mode - everyone uses challenge's timezone
    start, end = participant_window_utc(
        d, time(6), time(23), "challenge_tz", "America/Los_Angeles", "America/New_York"
    )
    
    # Uses EST, not PST: 6 AM EST = 11 AM UTC, 11 PM EST = 4 AM UTC next day
    assert start.hour == 11 and end.hour == 4


def test_participant_window_utc_fallback():
    """Test fallback to UTC when challenge_tz is None"""
    d = date(2025, 1, 10)
    
    start, end = participant_window_utc(
        d, time(6), time(23), "challenge_tz", "America/Los_Angeles", None
    )
    
    # Should fallback to UTC: 6 AM UTC = 6 AM UTC, 11 PM UTC = 11 PM UTC
    assert start.hour == 6 and end.hour == 23


def test_extreme_overnight_window():
    """Test extreme overnight window (23:59 to 00:01)"""
    d = date(2025, 1, 10)
    s_utc, e_utc = local_window_to_utc(d, time(23, 59), time(0, 1), "UTC")
    
    # Should be 2 minutes
    duration_minutes = (e_utc - s_utc).total_seconds() / 60
    assert duration_minutes == 2


def test_timezone_validation():
    """Test that invalid timezone raises appropriate error"""
    d = date(2025, 1, 10)
    
    with pytest.raises(Exception):  # Should raise ZoneInfo exception for invalid timezone
        local_window_to_utc(d, time(6), time(23), "Invalid/Timezone")


def test_same_start_end_time():
    """Test window where start equals end time"""
    d = date(2025, 1, 10)
    s_utc, e_utc = local_window_to_utc(d, time(12, 0), time(12, 0), "UTC")
    
    # Should be treated as overnight (24 hours)
    duration_hours = (e_utc - s_utc).total_seconds() / 3600
    assert duration_hours == 24


def test_utc_timezone():
    """Test UTC timezone handling"""
    d = date(2025, 1, 10)
    s_utc, e_utc = local_window_to_utc(d, time(6, 0), time(23, 0), "UTC")
    
    # UTC should pass through unchanged
    assert s_utc.hour == 6 and e_utc.hour == 23
    assert s_utc.date() == d and e_utc.date() == d


@pytest.mark.parametrize("tz_name,expected_offset_hours", [
    ("America/New_York", -5),    # EST = UTC-5
    ("America/Los_Angeles", -8), # PST = UTC-8  
    ("Europe/London", 0),        # GMT = UTC+0
    ("Asia/Tokyo", 9),           # JST = UTC+9
])
def test_various_timezones_standard_time(tz_name, expected_offset_hours):
    """Test various timezones during standard time"""
    d = date(2025, 1, 10)  # Standard time for all tested zones
    s_utc, e_utc = local_window_to_utc(d, time(12, 0), time(13, 0), tz_name)
    
    # Calculate expected UTC hour
    expected_utc_hour = (12 - expected_offset_hours) % 24
    assert s_utc.hour == expected_utc_hour