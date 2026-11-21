"""Database tables for LeaseMate.

companies ─< properties ─< units
                 │
                 └─< guest_cards ─< tours

- A company is a rental housing operator (the "tenant" in multi-tenant terms).
  Every property belongs to exactly one company, which is what lets us enforce
  tenant isolation later: an agent working for one company must never see
  another company's properties, units or leads.
- All money is in Indian rupees (INR), stored as whole numbers.
- Tour (site visit) times are stored in UTC. Each property stores its time zone
  ("Asia/Kolkata" for Pune), and we convert to local time only when talking to
  a prospect. IST is UTC+5:30, so a sloppy "add 5 hours" bug shows up quickly.
"""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))

    properties: Mapped[list["Property"]] = relationship(back_populates="company")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(200))
    locality: Mapped[str] = mapped_column(String(80), index=True)  # e.g. "Hinjewadi"
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(40))
    pincode: Mapped[str] = mapped_column(String(6))
    timezone: Mapped[str] = mapped_column(String(50))  # IANA name, e.g. "Asia/Kolkata"
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)

    amenities: Mapped[list[str]] = mapped_column(JSON, default=list)
    pet_policy: Mapped[str] = mapped_column(Text)
    parking: Mapped[str] = mapped_column(Text)
    current_offer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Leave and licence agreement terms (the standard rental agreement in Maharashtra).
    security_deposit_months: Mapped[int] = mapped_column(Integer)  # refundable, in months of rent
    lock_in_months: Mapped[int] = mapped_column(Integer)
    notice_period_days: Mapped[int] = mapped_column(Integer)
    agreement_notes: Mapped[str] = mapped_column(Text)

    # Site visit hours, in the property's local time. Days use Python's weekday(): 0 = Monday.
    tour_days: Mapped[list[int]] = mapped_column(JSON)
    tour_start_hour: Mapped[int] = mapped_column(Integer)  # 24-hour clock, e.g. 10
    tour_end_hour: Mapped[int] = mapped_column(Integer)  # last visit starts before this hour

    company: Mapped[Company] = relationship(back_populates="properties")
    units: Mapped[list["Unit"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    guest_cards: Mapped[list["GuestCard"]] = relationship(back_populates="property")


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)

    unit_number: Mapped[str] = mapped_column(String(10))  # wing-floor-flat, e.g. "B-1204"
    floor_plan: Mapped[str] = mapped_column(String(40))  # e.g. "2 BHK"
    bedrooms: Mapped[int] = mapped_column(Integer)  # 0 = 1 RK (one room + kitchen)
    bathrooms: Mapped[float] = mapped_column(Float)
    carpet_area_sqft: Mapped[int] = mapped_column(Integer)
    floor: Mapped[int] = mapped_column(Integer)
    furnishing: Mapped[str] = mapped_column(String(20))  # unfurnished | semi-furnished | fully furnished
    rent: Mapped[int] = mapped_column(Integer)  # INR per month
    maintenance: Mapped[int] = mapped_column(Integer)  # society maintenance, INR per month
    available_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="available")  # available | leased
    features: Mapped[list[str]] = mapped_column(JSON, default=list)

    property: Mapped[Property] = relationship(back_populates="units")


class GuestCard(Base):
    """A prospective tenant (a "lead"). Created by the agent during a conversation."""

    __tablename__ = "guest_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)

    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    desired_bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_move_in: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)  # INR per month
    pets: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(20), default="chat")  # chat | sms | email
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | tour_scheduled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    property: Mapped[Property] = relationship(back_populates="guest_cards")
    tours: Mapped[list["Tour"]] = relationship(back_populates="guest_card")


class Tour(Base):
    """A booked site visit."""

    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_card_id: Mapped[int] = mapped_column(ForeignKey("guest_cards.id"), index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime)  # always UTC
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    guest_card: Mapped[GuestCard] = relationship(back_populates="tours")
    
    


class Handoff(Base):
    """A conversation the AI passed to the human leasing team (negotiation, complaint, etc.)."""

    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    guest_card_id: Mapped[int | None] = mapped_column(ForeignKey("guest_cards.id"), nullable=True)

    # negotiation | complaint | resident_issue | human_requested | other
    reason: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)  # written by the agent for the leasing team
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)