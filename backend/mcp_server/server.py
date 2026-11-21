import os
import re
from datetime import date, datetime, time, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from pydantic import EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import GuestCard, Property, Tour, Unit, Handoff
from db.money import format_inr
from mcp_server import scheduling
from mcp_server.schemas import (
    AvailabilityResult,
    FloorPlanSummary,
    GuestCardResult,
    PropertyDetails,
    PropertySummary,
    TourConfirmation,
    TourSlots,
    UnitOption,
    HandoffResult
)

load_dotenv()

COMPANY_HEADER = "x-company-id"

mcp = FastMCP(
    name="LeaseMate Leasing Tools",
    instructions=(
        "Tools for a leasing assistant at a rental housing company in Pune, India. "
        "Use them to look up properties and flats, check availability and rent, "
        "create guest cards (leads) and book site visits. All prices are in INR."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_company_id() -> int:
    """The company this request is for. Set by the caller, never by the LLM."""
    # In production this would come from a verified auth token, not a plain header.
    value = get_http_headers().get(COMPANY_HEADER) or os.getenv("DEFAULT_COMPANY_ID")
    if not value or not value.isdigit():
        raise ToolError("No company context for this request.")
    return int(value)


def get_company_property(session: Session, property_id: int) -> Property:
    """Load a property, but only if it belongs to the current company."""
    prop = session.scalar(
        select(Property).where(
            Property.id == property_id,
            Property.company_id == current_company_id(),
        )
    )
    if prop is None:
        # Same message whether the property doesn't exist or belongs to another
        # company, so we never reveal that another company's property exists.
        raise ToolError(f"No property with id {property_id}. Use list_properties to see valid ids.")
    return prop


def normalize_indian_mobile(raw: str) -> str:
    """'98765 43210', '+91-9876543210', '09876543210' -> '+919876543210'."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ToolError(
            f"'{raw}' doesn't look like a valid Indian mobile number "
            "(10 digits starting with 6, 7, 8 or 9). Ask the prospect to check it."
        )
    return f"+91{digits}"


def to_unit_option(unit: Unit) -> UnitOption:
    prop = unit.property
    deposit = unit.rent * prop.security_deposit_months
    return UnitOption(
        unit_id=unit.id,
        property_id=prop.id,
        property_name=prop.name,
        unit_number=unit.unit_number,
        floor_plan=unit.floor_plan,
        bedrooms=unit.bedrooms,
        bathrooms=unit.bathrooms,
        carpet_area_sqft=unit.carpet_area_sqft,
        floor=unit.floor,
        furnishing=unit.furnishing,
        rent=unit.rent,
        rent_display=format_inr(unit.rent),
        maintenance=unit.maintenance,
        maintenance_display=format_inr(unit.maintenance),
        security_deposit=deposit,
        security_deposit_display=format_inr(deposit),
        available_on=unit.available_on,
        features=unit.features,
    )


def check_visit_date(day: date, tz: ZoneInfo) -> None:
    today = datetime.now(tz).date()
    if day < today:
        raise ToolError(f"{day} is in the past. Today is {today}.")
    if (day - today).days > scheduling.MAX_DAYS_AHEAD:
        raise ToolError(f"Site visits can only be booked up to {scheduling.MAX_DAYS_AHEAD} days ahead.")


def open_slots(session: Session, prop: Property, day: date) -> list[time]:
    """Slot start times on `day` that are within visit hours, not booked, and not too soon."""
    tz = ZoneInfo(prop.timezone)
    if day.weekday() not in prop.tour_days:
        return []

    start_utc, end_utc = scheduling.local_day_bounds_utc(day, tz)
    booked = {
        scheduling.utc_to_local(starts_at, tz).time()
        for starts_at in session.scalars(
            select(Tour.starts_at).where(
                Tour.property_id == prop.id,
                Tour.status == "scheduled",
                Tour.starts_at >= start_utc,
                Tour.starts_at < end_utc,
            )
        )
    }
    earliest = datetime.now(tz) + scheduling.MIN_NOTICE

    return [
        slot
        for slot in scheduling.candidate_slots(prop.tour_start_hour, prop.tour_end_hour)
        if slot not in booked and datetime.combine(day, slot, tzinfo=tz) >= earliest
    ]


# ---------------------------------------------------------------------------
# Tools (the docstrings are what the LLM reads, so they matter)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True})
def list_properties() -> list[PropertySummary]:
    """List all rental properties, with the starting rent for each flat type that
    has availability. Call this when the prospect hasn't chosen a property yet."""
    with SessionLocal() as session:
        properties = session.scalars(
            select(Property)
            .where(Property.company_id == current_company_id())
            .order_by(Property.id)
        ).all()

        results = []
        for prop in properties:
            rows = session.execute(
                select(Unit.floor_plan, func.count(), func.min(Unit.rent))
                .where(Unit.property_id == prop.id, Unit.status == "available")
                .group_by(Unit.bedrooms, Unit.floor_plan)
                .order_by(Unit.bedrooms)
            ).all()

            results.append(
                PropertySummary(
                    property_id=prop.id,
                    name=prop.name,
                    locality=prop.locality,
                    description=prop.description,
                    current_offer=prop.current_offer,
                    floor_plans=[
                        FloorPlanSummary(
                            floor_plan=plan,
                            available_units=count,
                            rent_from=min_rent,
                            rent_from_display=format_inr(min_rent),
                        )
                        for plan, count, min_rent in rows
                    ],
                )
            )
        return results


@mcp.tool(annotations={"readOnlyHint": True})
def get_property_details(
    property_id: Annotated[int, Field(description="Property id from list_properties")],
) -> PropertyDetails:
    """Get full details of one property: address, amenities, pet policy, parking,
    security deposit, lock-in, notice period, agreement process and site visit hours."""
    with SessionLocal() as session:
        prop = get_company_property(session, property_id)
        hours = (
            f"{scheduling.format_hour(prop.tour_start_hour)} to "
            f"{scheduling.format_hour(prop.tour_end_hour)}, {scheduling.describe_days(prop.tour_days)}"
        )
        return PropertyDetails(
            property_id=prop.id,
            name=prop.name,
            address=prop.address,
            locality=prop.locality,
            city=prop.city,
            phone=prop.phone,
            email=prop.email,
            description=prop.description,
            amenities=prop.amenities,
            pet_policy=prop.pet_policy,
            parking=prop.parking,
            current_offer=prop.current_offer,
            security_deposit_months=prop.security_deposit_months,
            lock_in_months=prop.lock_in_months,
            notice_period_days=prop.notice_period_days,
            agreement_notes=prop.agreement_notes,
            site_visit_hours=hours,
        )


@mcp.tool(annotations={"readOnlyHint": True})
def check_availability(
    property_id: Annotated[
        int | None, Field(description="Limit the search to one property. Leave empty to search all.")
    ] = None,
    bedrooms: Annotated[
        int | None,
        Field(ge=0, le=5, description="0 = 1 RK, 1 = 1 BHK, 2 = 2 BHK, 3 = 3 BHK"),
    ] = None,
    max_rent: Annotated[int | None, Field(gt=0, description="Maximum monthly rent in INR")] = None,
    move_in_date: Annotated[
        date | None,
        Field(description="Desired move-in date (YYYY-MM-DD). Only flats available by then are returned."),
    ] = None,
    furnishing: Literal["unfurnished", "semi-furnished", "fully furnished"] | None = None,
    limit: Annotated[int, Field(ge=1, le=10, description="Maximum number of flats to return")] = 5,
) -> AvailabilityResult:
    """Search available flats with their current rent, maintenance and security deposit,
    cheapest first. Always use this for prices and availability; never guess them."""
    with SessionLocal() as session:
        query = (
            select(Unit)
            .join(Unit.property)
            .where(Property.company_id == current_company_id(), Unit.status == "available")
        )
        if property_id is not None:
            get_company_property(session, property_id)  # raises if not this company's property
            query = query.where(Unit.property_id == property_id)
        if bedrooms is not None:
            query = query.where(Unit.bedrooms == bedrooms)
        if furnishing is not None:
            query = query.where(Unit.furnishing == furnishing)
        if move_in_date is not None:
            query = query.where(Unit.available_on <= move_in_date)

        query_without_budget = query
        if max_rent is not None:
            query = query.where(Unit.rent <= max_rent)

        units = session.scalars(query.order_by(Unit.rent)).all()

        if units:
            message = f"Found {len(units)} matching flats, cheapest first."
            if len(units) > limit:
                message += f" Showing the first {limit}."
        else:
            message = "No flats match all of these filters."
            if max_rent is not None:
                cheapest = session.scalars(query_without_budget.order_by(Unit.rent).limit(1)).first()
                if cheapest is not None:
                    message += (
                        f" Without the budget limit, the lowest rent is {format_inr(cheapest.rent)}"
                        f" ({cheapest.floor_plan} at {cheapest.property.name})."
                    )
            message += " Suggest relaxing a filter, such as budget, move-in date or furnishing."

        return AvailabilityResult(
            total_matches=len(units),
            matches=[to_unit_option(unit) for unit in units[:limit]],
            message=message,
        )


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
def create_guest_card(
    property_id: Annotated[int, Field(description="The property the prospect is interested in")],
    first_name: Annotated[str, Field(min_length=1, max_length=60)],
    last_name: Annotated[str, Field(min_length=1, max_length=60)],
    phone: Annotated[str | None, Field(description="Indian mobile number")] = None,
    email: EmailStr | None = None,
    desired_bedrooms: Annotated[int | None, Field(ge=0, le=5, description="0 = 1 RK")] = None,
    desired_move_in: Annotated[date | None, Field(description="YYYY-MM-DD")] = None,
    max_budget: Annotated[int | None, Field(gt=0, description="Monthly budget in INR")] = None,
    pets: Annotated[str | None, Field(max_length=120, description="e.g. 'one dog'")] = None,
    notes: Annotated[
        str | None,
        Field(max_length=500, description="Anything else useful for the leasing team"),
    ] = None,
    source: Literal["chat", "sms", "email"] = "chat",
) -> GuestCardResult:
    """Create a guest card (lead) for a prospect at a property. Needs their name and a
    mobile number or email. If the same person already has a guest card at this
    property, it is updated instead of creating a duplicate."""
    if not phone and not email:
        raise ToolError("Ask the prospect for a mobile number or email before creating a guest card.")

    with SessionLocal() as session:
        prop = get_company_property(session, property_id)
        phone_normalized = normalize_indian_mobile(phone) if phone else None
        email_normalized = email.lower() if email else None

        # Match an existing guest card at this property by phone or email.
        same_person = []
        if phone_normalized:
            same_person.append(GuestCard.phone == phone_normalized)
        if email_normalized:
            same_person.append(GuestCard.email == email_normalized)
        card = session.scalar(
            select(GuestCard).where(GuestCard.property_id == prop.id, or_(*same_person))
        )

        is_new = card is None
        if is_new:
            card = GuestCard(property_id=prop.id, first_name=first_name, last_name=last_name, source=source)
            session.add(card)

        # Only overwrite fields the prospect actually gave us, so we never wipe existing data.
        updates = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone_normalized,
            "email": email_normalized,
            "desired_bedrooms": desired_bedrooms,
            "desired_move_in": desired_move_in,
            "max_budget": max_budget,
            "pets": pets,
            "notes": notes,
        }
        for field, value in updates.items():
            if value is not None:
                setattr(card, field, value)

        session.commit()

        message = (
            "Guest card created."
            if is_new
            else "This prospect already had a guest card at this property, so it was updated."
        )
        return GuestCardResult(
            guest_card_id=card.id,
            property_id=prop.id,
            property_name=prop.name,
            first_name=card.first_name,
            last_name=card.last_name,
            status=card.status,
            is_new=is_new,
            message=message,
        )


@mcp.tool(annotations={"readOnlyHint": True})
def get_tour_slots(
    property_id: int,
    visit_date: Annotated[date, Field(description="Date of the site visit (YYYY-MM-DD)")],
) -> TourSlots:
    """Get the open site visit times at a property on a given date, in local time (IST).
    Call this before book_tour and only offer times from this list."""
    with SessionLocal() as session:
        prop = get_company_property(session, property_id)
        tz = ZoneInfo(prop.timezone)
        check_visit_date(visit_date, tz)
        slots = open_slots(session, prop, visit_date)

        if visit_date.weekday() not in prop.tour_days:
            day_name = scheduling.DAY_NAMES[visit_date.weekday()]
            message = (
                f"No site visits on {day_name}s. "
                f"Visits run {scheduling.describe_days(prop.tour_days)}."
            )
        elif not slots:
            message = "No open times left on this date. Suggest another day."
        else:
            message = f"{len(slots)} open times, each {scheduling.SLOT_MINUTES} minutes, in local time."

        return TourSlots(
            property_id=prop.id,
            property_name=prop.name,
            date=visit_date,
            timezone=prop.timezone,
            slot_minutes=scheduling.SLOT_MINUTES,
            available_times=[slot.strftime("%H:%M") for slot in slots],
            message=message,
        )


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False})
def book_tour(
    property_id: int,
    guest_card_id: Annotated[int, Field(description="From create_guest_card")],
    visit_date: Annotated[date, Field(description="YYYY-MM-DD")],
    start_time: Annotated[
        str,
        Field(
            pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
            description="Local start time, 24-hour HH:MM, taken from get_tour_slots",
        ),
    ],
) -> TourConfirmation:
    """Book a site visit for a prospect who has a guest card. If they already have an
    upcoming visit at this property, it is moved to the new time (a reschedule)."""
    with SessionLocal() as session:
        prop = get_company_property(session, property_id)
        tz = ZoneInfo(prop.timezone)

        card = session.get(GuestCard, guest_card_id)
        if card is None or card.property_id != prop.id:
            raise ToolError(
                f"No guest card {guest_card_id} at {prop.name}. Create one with create_guest_card first."
            )

        check_visit_date(visit_date, tz)
        slot = time.fromisoformat(start_time)
        available = open_slots(session, prop, visit_date)
        if slot not in available:
            options = ", ".join(s.strftime("%H:%M") for s in available) or "none"
            raise ToolError(f"{start_time} isn't available on {visit_date}. Open times: {options}.")

        # Reschedule: cancel any upcoming visit this prospect already has here.
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        upcoming = session.scalars(
            select(Tour).where(
                Tour.guest_card_id == card.id,
                Tour.property_id == prop.id,
                Tour.status == "scheduled",
                Tour.starts_at >= now_utc,
            )
        ).all()
        rescheduled_from = None
        for old_tour in upcoming:
            old_tour.status = "cancelled"
            rescheduled_from = scheduling.format_local(scheduling.utc_to_local(old_tour.starts_at, tz))

        tour = Tour(
            guest_card_id=card.id,
            property_id=prop.id,
            starts_at=scheduling.local_to_utc(visit_date, slot, tz),
        )
        session.add(tour)
        card.status = "tour_scheduled"
        session.commit()

        starts_local = scheduling.format_local(scheduling.utc_to_local(tour.starts_at, tz))
        message = f"Site visit booked for {starts_local}."
        if rescheduled_from:
            message += f" It replaces the earlier visit on {rescheduled_from}."

        return TourConfirmation(
            tour_id=tour.id,
            guest_card_id=card.id,
            property_name=prop.name,
            address=prop.address,
            starts_at_local=starts_local,
            starts_at_utc=tour.starts_at,
            duration_minutes=scheduling.SLOT_MINUTES,
            leasing_office_phone=prop.phone,
            rescheduled_from=rescheduled_from,
            message=message,
        )
        
@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False})
def request_human_handoff(
    reason: Literal["negotiation", "complaint", "resident_issue", "human_requested", "other"],
    summary: Annotated[
        str,
        Field(min_length=10, max_length=600, description="What the person needs, written for the leasing team"),
    ],
    property_id: Annotated[int | None, Field(description="The property it's about, if known")] = None,
    guest_card_id: Annotated[int | None, Field(description="The prospect's guest card, if one exists")] = None,
) -> HandoffResult:
    """Pass the conversation to the human leasing team. Use this for rent or deposit
    negotiation, requests to waive or reduce charges, complaints, existing residents'
    maintenance issues, or when the person asks to talk to a human. Never promise
    discounts or exceptions yourself."""
    with SessionLocal() as session:
        company_id = current_company_id()
        prop = get_company_property(session, property_id) if property_id is not None else None

        if guest_card_id is not None:
            card = session.get(GuestCard, guest_card_id)
            # The guest card must belong to one of this company's properties.
            if card is None or card.property.company_id != company_id:
                raise ToolError(f"No guest card {guest_card_id}. Leave guest_card_id empty if unsure.")
            prop = prop or card.property

        # Share the property's leasing office number, or the company's first property if unknown.
        contact = prop or session.scalars(
            select(Property).where(Property.company_id == company_id).order_by(Property.id)
        ).first()

        handoff = Handoff(
            company_id=company_id,
            property_id=prop.id if prop else None,
            guest_card_id=guest_card_id,
            reason=reason,
            summary=summary,
        )
        session.add(handoff)
        session.commit()

        return HandoffResult(
            handoff_id=handoff.id,
            status=handoff.status,
            contact_phone=contact.phone,
            message=(
                f"Handoff #{handoff.id} created. The leasing team will follow up. "
                f"The person can also call {contact.phone}."
            ),
        )


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)