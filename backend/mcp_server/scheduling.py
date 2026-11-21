"""Site visit scheduling helpers: time zones and slot maths.

These are plain functions with no database or MCP code, so they are easy to
unit test. Rules:
- Times are stored in the database as UTC (without tzinfo, because SQLite has
  no time zone support).
- Prospects always see the property's local time (IST for Pune).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

SLOT_MINUTES = 30
MAX_DAYS_AHEAD = 30
MIN_NOTICE = timedelta(hours=1)  # can't book a visit starting in the next hour

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def candidate_slots(start_hour: int, end_hour: int, slot_minutes: int = SLOT_MINUTES) -> list[time]:
    """All slot start times between start_hour and end_hour, e.g. 10:00, 10:30, ... 18:30."""
    slots = []
    current = datetime.combine(date.min, time(start_hour))
    end = datetime.combine(date.min, time(end_hour))
    while current < end:
        slots.append(current.time())
        current += timedelta(minutes=slot_minutes)
    return slots


def local_to_utc(day: date, start: time, tz: ZoneInfo) -> datetime:
    """Local date + time -> naive UTC datetime, ready to store in the database."""
    local = datetime.combine(day, start, tzinfo=tz)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(stored_utc: datetime, tz: ZoneInfo) -> datetime:
    """Naive UTC datetime from the database -> timezone-aware local datetime."""
    return stored_utc.replace(tzinfo=timezone.utc).astimezone(tz)


def local_day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """The UTC start and end of a local calendar day (for database range queries)."""
    start = local_to_utc(day, time(0), tz)
    return start, start + timedelta(days=1)


def format_local(dt_local: datetime) -> str:
    """'Saturday, 22 Nov 2026 at 11:00 AM IST'. Avoids %-I, which doesn't work on Windows."""
    clock = dt_local.strftime("%I:%M %p").lstrip("0")
    return f"{dt_local:%A}, {dt_local.day} {dt_local:%b %Y} at {clock} {dt_local.tzname()}"


def format_hour(hour: int) -> str:
    """13 -> '1:00 PM'."""
    return time(hour).strftime("%I:%M %p").lstrip("0")


def describe_days(days: list[int]) -> str:
    """[0..6] -> 'every day', [0..5] -> 'Monday to Saturday', otherwise a list of names."""
    days = sorted(days)
    if days == list(range(7)):
        return "every day"
    if days == list(range(days[0], days[-1] + 1)) and len(days) > 2:
        return f"{DAY_NAMES[days[0]]} to {DAY_NAMES[days[-1]]}"
    return ", ".join(DAY_NAMES[d] for d in days)