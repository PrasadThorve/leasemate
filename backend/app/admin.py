from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import get_admin_company_id
from db.database import SessionLocal
from db.models import Company, GuestCard, Handoff, Property, Tour
from db.money import format_inr
from mcp_server import scheduling

router = APIRouter(prefix="/admin", tags=["admin"])

IST = ZoneInfo("Asia/Kolkata")


class LeadRow(BaseModel):
    id: int
    name: str
    phone: str | None
    email: str | None
    property_name: str
    wants: str | None  # e.g. "2 BHK"
    budget: str | None  # e.g. "₹25,000"
    move_in: str | None  # e.g. "1 Dec 2026"
    pets: str | None
    status: str  # new | tour_scheduled
    created_at: str  # e.g. "Sat 21 Nov, 4:35 PM"


class TourRow(BaseModel):
    id: int
    visit_time: str  # e.g. "Sun 22 Nov, 11:00 AM"
    property_name: str
    visitor: str
    phone: str | None
    status: str  # scheduled | cancelled
    booked_at: str


class HandoffRow(BaseModel):
    id: int
    reason: str  # negotiation | complaint | resident_issue | human_requested | other
    summary: str  # written by the agent for the leasing team
    property_name: str | None
    lead_name: str | None
    status: str  # open | resolved
    created_at: str


class ActivityResponse(BaseModel):
    company_name: str
    leads: list[LeadRow]
    tours: list[TourRow]
    handoffs: list[HandoffRow]


def local_time(stored_utc: datetime, tz: ZoneInfo = IST) -> str:
    """Naive UTC from the database -> 'Sun 22 Nov, 11:00 AM' in local time."""
    local = scheduling.utc_to_local(stored_utc, tz)
    return f"{local:%a} {local.day} {local:%b}, {local.strftime('%I:%M %p').lstrip('0')}"


def display_phone(phone: str | None) -> str | None:
    """'+919876543210' -> '+91 98765 43210' (how Indian mobiles are usually written)."""
    if phone and phone.startswith("+91") and len(phone) == 13:
        return f"+91 {phone[3:8]} {phone[8:]}"
    return phone


def short_date(day: date | None) -> str | None:
    return f"{day.day} {day:%b %Y}" if day else None


def full_name(card: GuestCard) -> str:
    return f"{card.first_name} {card.last_name}"


def flat_type(bedrooms: int | None) -> str | None:
    if bedrooms is None:
        return None
    return "1 RK" if bedrooms == 0 else f"{bedrooms} BHK"


@router.get("/activity", response_model=ActivityResponse)
def activity(company_id: Annotated[int, Depends(get_admin_company_id)]) -> ActivityResponse:
    with SessionLocal() as session:
        company = session.get(Company, company_id)
        # Only this company's properties, so everything below is automatically company-scoped.
        properties = {
            p.id: p for p in session.scalars(select(Property).where(Property.company_id == company_id))
        }

        cards = session.scalars(
            select(GuestCard)
            .where(GuestCard.property_id.in_(properties))
            .order_by(GuestCard.created_at.desc())
        ).all()
        tours = session.scalars(
            select(Tour).where(Tour.property_id.in_(properties)).order_by(Tour.created_at.desc())
        ).all()
        handoffs = session.scalars(
            select(Handoff).where(Handoff.company_id == company_id).order_by(Handoff.created_at.desc())
        ).all()

        cards_by_id = {card.id: card for card in cards}

        def tz_of(property_id: int | None) -> ZoneInfo:
            prop = properties.get(property_id)
            return ZoneInfo(prop.timezone) if prop else IST

        return ActivityResponse(
            company_name=company.name,
            leads=[
                LeadRow(
                    id=card.id,
                    name=full_name(card),
                    phone=display_phone(card.phone),
                    email=card.email,
                    property_name=properties[card.property_id].name,
                    wants=flat_type(card.desired_bedrooms),
                    budget=format_inr(card.max_budget) if card.max_budget else None,
                    move_in=short_date(card.desired_move_in),
                    pets=card.pets,
                    status=card.status,
                    created_at=local_time(card.created_at, tz_of(card.property_id)),
                )
                for card in cards
            ],
            tours=[
                TourRow(
                    id=tour.id,
                    visit_time=local_time(tour.starts_at, tz_of(tour.property_id)),
                    property_name=properties[tour.property_id].name,
                    visitor=full_name(tour.guest_card),
                    phone=display_phone(tour.guest_card.phone),
                    status=tour.status,
                    booked_at=local_time(tour.created_at, tz_of(tour.property_id)),
                )
                for tour in tours
            ],
            handoffs=[
                HandoffRow(
                    id=handoff.id,
                    reason=handoff.reason,
                    summary=handoff.summary,
                    property_name=properties[handoff.property_id].name if handoff.property_id else None,
                    lead_name=(
                        full_name(cards_by_id[handoff.guest_card_id])
                        if handoff.guest_card_id in cards_by_id
                        else None
                    ),
                    status=handoff.status,
                    created_at=local_time(handoff.created_at, tz_of(handoff.property_id)),
                )
                for handoff in handoffs
            ],
        )