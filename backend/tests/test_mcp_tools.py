from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastmcp.exceptions import ToolError
from sqlalchemy import select

from db.database import SessionLocal
from db.models import Handoff
from db.money import format_inr

IST = ZoneInfo("Asia/Kolkata")
SAHYADRI_PROPERTIES = ["Mulberry Heights", "Riverstone Residences", "Banyan Court"]


async def call(client, tool: str, **arguments):
    """Call a tool and return its structured result as plain dicts/lists."""
    result = await client.call_tool(tool, arguments)
    data = result.structured_content
    # Tools that return a list come back wrapped as {"result": [...]}.
    return data["result"] if list(data) == ["result"] else data


def today_ist() -> date:
    return datetime.now(IST).date()


async def new_guest_card(client, property_id: int = 1, phone: str = "9876543210") -> int:
    card = await call(
        client, "create_guest_card", property_id=property_id, first_name="Asha", last_name="Patil", phone=phone
    )
    return card["guest_card_id"]


# --- Tenant isolation ---------------------------------------------------------

async def test_list_properties_only_shows_own_company(mcp_client):
    properties = await call(mcp_client, "list_properties")
    assert [p["name"] for p in properties] == SAHYADRI_PROPERTIES


async def test_company_header_decides_the_company(mcp_client, monkeypatch):
    # Pretend our backend sent "x-company-id: 2" (Indrayani Homes). The header wins over DEFAULT_COMPANY_ID.
    monkeypatch.setattr("mcp_server.server.get_http_headers", lambda: {"x-company-id": "2"})
    properties = await call(mcp_client, "list_properties")
    assert [p["name"] for p in properties] == ["Lotus Court"]


async def test_no_company_context_is_refused(mcp_client, monkeypatch):
    monkeypatch.delenv("DEFAULT_COMPANY_ID")
    with pytest.raises(ToolError, match="No company context"):
        await call(mcp_client, "list_properties")


@pytest.mark.parametrize("tool", ["get_property_details", "check_availability"])
async def test_other_companys_property_looks_like_it_does_not_exist(mcp_client, tool):
    # Property 4 (Lotus Court) belongs to Indrayani Homes, not Sahyadri.
    with pytest.raises(ToolError, match="No property with id 4"):
        await call(mcp_client, tool, property_id=4)


# --- Availability and prices --------------------------------------------------

async def test_availability_filters_and_sorts_cheapest_first(mcp_client):
    result = await call(mcp_client, "check_availability", bedrooms=2, limit=10)
    rents = [flat["rent"] for flat in result["matches"]]

    assert result["total_matches"] > 0
    assert all(flat["floor_plan"] == "2 BHK" for flat in result["matches"])
    assert all(flat["property_name"] in SAHYADRI_PROPERTIES for flat in result["matches"])
    assert rents == sorted(rents)


async def test_availability_respects_budget_and_move_in_date(mcp_client):
    result = await call(mcp_client, "check_availability", max_rent=20000, move_in_date=str(today_ist()), limit=10)
    for flat in result["matches"]:
        assert flat["rent"] <= 20000
        assert date.fromisoformat(flat["available_on"]) <= today_ist()


async def test_no_match_suggests_the_cheapest_option(mcp_client):
    result = await call(mcp_client, "check_availability", bedrooms=3, max_rent=1000)
    assert result["total_matches"] == 0
    assert "Without the budget limit, the lowest rent is ₹" in result["message"]


async def test_deposit_is_rent_times_deposit_months(mcp_client):
    # Mulberry Heights asks for a 2-month deposit.
    result = await call(mcp_client, "check_availability", property_id=1, limit=10)
    for flat in result["matches"]:
        assert flat["security_deposit"] == flat["rent"] * 2
        assert flat["security_deposit_display"] == format_inr(flat["rent"] * 2)
        assert flat["rent_display"] == format_inr(flat["rent"])


async def test_invalid_arguments_are_rejected_by_validation(mcp_client):
    with pytest.raises(ToolError, match="less than or equal to 5"):
        await call(mcp_client, "check_availability", bedrooms=9)


# --- Guest cards ----------------------------------------------------------------

async def test_guest_card_normalizes_phone_and_avoids_duplicates(mcp_client):
    first = await call(
        mcp_client, "create_guest_card", property_id=1, first_name="Asha", last_name="Patil", phone="98765 43210"
    )
    # Same person, phone written differently: the existing card is updated, not duplicated.
    second = await call(
        mcp_client, "create_guest_card", property_id=1, first_name="Asha", last_name="Patil",
        phone="+91-98765-43210", max_budget=25000,
    )
    assert first["is_new"] is True
    assert second["is_new"] is False
    assert second["guest_card_id"] == first["guest_card_id"]


async def test_guest_card_rejects_an_invalid_phone(mcp_client):
    with pytest.raises(ToolError, match="valid Indian mobile number"):
        await new_guest_card(mcp_client, phone="12345")


async def test_guest_card_needs_phone_or_email(mcp_client):
    with pytest.raises(ToolError, match="mobile number or email"):
        await call(mcp_client, "create_guest_card", property_id=1, first_name="Asha", last_name="Patil")


# --- Site visits ------------------------------------------------------------------

async def test_book_then_reschedule_frees_the_old_slot(mcp_client):
    card_id = await new_guest_card(mcp_client)
    tomorrow = str(today_ist() + timedelta(days=1))

    slots = await call(mcp_client, "get_tour_slots", property_id=1, visit_date=tomorrow)
    assert slots["available_times"][0] == "10:00"
    assert len(slots["available_times"]) == 18

    first = await call(
        mcp_client, "book_tour", property_id=1, guest_card_id=card_id, visit_date=tomorrow, start_time="10:00"
    )
    assert first["rescheduled_from"] is None
    assert first["starts_at_local"].endswith("at 10:00 AM IST")

    second = await call(
        mcp_client, "book_tour", property_id=1, guest_card_id=card_id, visit_date=tomorrow, start_time="11:00"
    )
    assert second["rescheduled_from"] is not None  # the 10:00 visit was moved, not duplicated

    slots = await call(mcp_client, "get_tour_slots", property_id=1, visit_date=tomorrow)
    assert "10:00" in slots["available_times"]  # freed again
    assert "11:00" not in slots["available_times"]


async def test_a_slot_cannot_be_double_booked(mcp_client):
    tomorrow = str(today_ist() + timedelta(days=1))
    asha = await new_guest_card(mcp_client, phone="9876543210")
    ravi = await new_guest_card(mcp_client, phone="9123456789")

    await call(mcp_client, "book_tour", property_id=1, guest_card_id=asha, visit_date=tomorrow, start_time="11:00")
    with pytest.raises(ToolError, match="isn't available"):
        await call(mcp_client, "book_tour", property_id=1, guest_card_id=ravi, visit_date=tomorrow, start_time="11:00")


@pytest.mark.parametrize(
    ("days_from_today", "error"),
    [(-1, "in the past"), (31, "up to 30 days ahead")],
)
async def test_visit_dates_must_be_within_range(mcp_client, days_from_today, error):
    visit_date = str(today_ist() + timedelta(days=days_from_today))
    with pytest.raises(ToolError, match=error):
        await call(mcp_client, "get_tour_slots", property_id=1, visit_date=visit_date)


async def test_no_visits_on_closed_days(mcp_client, monkeypatch):
    # Lotus Court (company 2) only does visits Monday to Saturday.
    monkeypatch.setenv("DEFAULT_COMPANY_ID", "2")
    next_sunday = today_ist() + timedelta(days=(6 - today_ist().weekday()) or 7)

    slots = await call(mcp_client, "get_tour_slots", property_id=4, visit_date=str(next_sunday))
    assert slots["available_times"] == []
    assert "No site visits on Sundays" in slots["message"]


# --- Handoffs ---------------------------------------------------------------------

async def test_handoff_is_saved_with_the_property_phone(mcp_client):
    result = await call(
        mcp_client, "request_human_handoff", reason="negotiation",
        summary="Wants ₹2,000 off the rent for a 2 BHK.", property_id=1,
    )
    assert result["contact_phone"] == "+91 20 0000 1101"

    with SessionLocal() as session:
        handoff = session.scalar(select(Handoff))
    assert (handoff.company_id, handoff.property_id, handoff.reason) == (1, 1, "negotiation")


async def test_handoff_cannot_use_another_companys_guest_card(mcp_client, monkeypatch):
    monkeypatch.setenv("DEFAULT_COMPANY_ID", "2")
    indrayani_card = await new_guest_card(mcp_client, property_id=4)
    monkeypatch.setenv("DEFAULT_COMPANY_ID", "1")

    with pytest.raises(ToolError, match=f"No guest card {indrayani_card}"):
        await call(
            mcp_client, "request_human_handoff", reason="complaint",
            summary="Complaint about a noisy neighbour.", guest_card_id=indrayani_card,
        )