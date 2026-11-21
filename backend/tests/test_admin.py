
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from db.database import SessionLocal
from db.models import GuestCard, Handoff, Tour
from mcp_server.scheduling import local_to_utc

SAHYADRI_ADMIN = {"X-Admin-Key": "sahyadri-admin-demo"}
INDRAYANI_ADMIN = {"X-Admin-Key": "indrayani-admin-demo"}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def activity_data():
    """What the agent would have saved: a lead with a visit and a handoff at Sahyadri,
    and one lead at Indrayani Homes (property 4)."""
    with SessionLocal() as session:
        asha = GuestCard(
            property_id=1, first_name="Asha", last_name="Patil", phone="+919876543210",
            desired_bedrooms=2, max_budget=25000, desired_move_in=date(2026, 12, 1), status="tour_scheduled",
        )
        ravi = GuestCard(property_id=4, first_name="Ravi", last_name="Kulkarni", phone="+919123456789")
        session.add_all([asha, ravi])
        session.flush()  # gives asha an id, needed below

        # A visit at 11:00 AM IST tomorrow. The database stores it in UTC (05:30).
        tomorrow = date.today() + timedelta(days=1)
        visit_utc = local_to_utc(tomorrow, time(11, 0), ZoneInfo("Asia/Kolkata"))
        session.add(Tour(guest_card_id=asha.id, property_id=1, starts_at=visit_utc))
        session.add(Handoff(
            company_id=1, property_id=1, guest_card_id=asha.id, reason="negotiation",
            summary="Wants ₹2,000 off the rent for a 2-year agreement.",
        ))
        session.commit()


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no key at all
        {"X-Admin-Key": "made-up-key"},
        {"X-Admin-Key": "sahyadri-demo-key"},  # the PUBLIC widget key must not open the dashboard
        {"X-Widget-Key": "sahyadri-demo-key"},
    ],
)
def test_dashboard_needs_the_secret_admin_key(client, headers):
    assert client.get("/admin/activity", headers=headers).status_code == 401


def test_dashboard_shows_what_the_agent_did(client, activity_data):
    body = client.get("/admin/activity", headers=SAHYADRI_ADMIN).json()

    assert body["company_name"] == "Sahyadri Rental Communities"
    [lead] = body["leads"]
    assert (lead["name"], lead["property_name"], lead["wants"], lead["budget"]) == (
        "Asha Patil", "Mulberry Heights", "2 BHK", "₹25,000",
    )

    [tour] = body["tours"]
    assert tour["visitor"] == "Asha Patil"
    assert tour["visit_time"].endswith("11:00 AM")  # shown in IST, not the stored UTC time
    assert tour["status"] == "scheduled"

    [handoff] = body["handoffs"]
    assert (handoff["reason"], handoff["lead_name"], handoff["status"]) == ("negotiation", "Asha Patil", "open")


def test_each_company_sees_only_its_own_activity(client, activity_data):
    indrayani = client.get("/admin/activity", headers=INDRAYANI_ADMIN).json()
    assert [lead["name"] for lead in indrayani["leads"]] == ["Ravi Kulkarni"]
    assert indrayani["tours"] == []
    assert indrayani["handoffs"] == []

    sahyadri = client.get("/admin/activity", headers=SAHYADRI_ADMIN).json()
    assert "Ravi Kulkarni" not in [lead["name"] for lead in sahyadri["leads"]]


def test_empty_dashboard(client):
    body = client.get("/admin/activity", headers=SAHYADRI_ADMIN).json()
    assert (body["leads"], body["tours"], body["handoffs"]) == ([], [], [])