from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from db.money import format_inr
from mcp_server import scheduling

IST = ZoneInfo("Asia/Kolkata")


def test_ist_is_converted_to_utc():
    # IST is UTC+5:30, so 10:00 AM in Pune is 04:30 UTC.
    assert scheduling.local_to_utc(date(2026, 11, 22), time(10, 0), IST) == datetime(2026, 11, 22, 4, 30)


def test_utc_to_local_round_trip():
    stored = scheduling.local_to_utc(date(2026, 11, 22), time(11, 0), IST)
    back = scheduling.utc_to_local(stored, IST)
    assert (back.date(), back.time()) == (date(2026, 11, 22), time(11, 0))


def test_candidate_slots_cover_visit_hours():
    slots = scheduling.candidate_slots(10, 19)
    assert len(slots) == 18  # 9 hours x 2 slots per hour
    assert slots[0] == time(10, 0)
    assert slots[-1] == time(18, 30)  # the last visit must END by 7 PM


def test_local_day_bounds_utc():
    start, end = scheduling.local_day_bounds_utc(date(2026, 11, 22), IST)
    # Midnight IST on the 22nd is 18:30 UTC on the 21st.
    assert start == datetime(2026, 11, 21, 18, 30)
    assert end == datetime(2026, 11, 22, 18, 30)


def test_format_local():
    visit = datetime(2026, 11, 22, 11, 0, tzinfo=IST)
    assert scheduling.format_local(visit) == "Sunday, 22 Nov 2026 at 11:00 AM IST"


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        ([0, 1, 2, 3, 4, 5, 6], "every day"),
        ([0, 1, 2, 3, 4, 5], "Monday to Saturday"),
        ([5, 6], "Saturday, Sunday"),
    ],
)
def test_describe_days(days, expected):
    assert scheduling.describe_days(days) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, "₹0"),
        (950, "₹950"),
        (9500, "₹9,500"),
        (125000, "₹1,25,000"),  # Indian grouping: lakhs, not "125,000"
        (12500000, "₹1,25,00,000"),  # 1.25 crore
        (-1500, "-₹1,500"),
    ],
)
def test_format_inr(amount, expected):
    assert format_inr(amount) == expected