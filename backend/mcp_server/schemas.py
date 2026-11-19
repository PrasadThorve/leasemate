"""Pydantic models for what the MCP tools return.

FastMCP turns these into JSON schemas, so the agent (and any MCP client) knows the
exact shape of every tool result. Prices come as a number and as a ready-made
display string ("₹23,000"), so the LLM never has to format money itself.
"""
from datetime import date, datetime

from pydantic import BaseModel


class FloorPlanSummary(BaseModel):
    floor_plan: str  # e.g. "2 BHK"
    available_units: int
    rent_from: int
    rent_from_display: str


class PropertySummary(BaseModel):
    property_id: int
    name: str
    locality: str
    description: str
    current_offer: str | None
    floor_plans: list[FloorPlanSummary]


class PropertyDetails(BaseModel):
    property_id: int
    name: str
    address: str
    locality: str
    city: str
    phone: str
    email: str
    description: str
    amenities: list[str]
    pet_policy: str
    parking: str
    current_offer: str | None
    security_deposit_months: int
    lock_in_months: int
    notice_period_days: int
    agreement_notes: str
    site_visit_hours: str  # e.g. "10:00 AM to 7:00 PM, every day"


class UnitOption(BaseModel):
    unit_id: int
    property_id: int
    property_name: str
    unit_number: str
    floor_plan: str
    bedrooms: int
    bathrooms: float
    carpet_area_sqft: int
    floor: int
    furnishing: str
    rent: int
    rent_display: str
    maintenance: int
    maintenance_display: str
    security_deposit: int
    security_deposit_display: str
    available_on: date
    features: list[str]


class AvailabilityResult(BaseModel):
    total_matches: int
    matches: list[UnitOption]
    message: str


class GuestCardResult(BaseModel):
    guest_card_id: int
    property_id: int
    property_name: str
    first_name: str
    last_name: str
    status: str
    is_new: bool  # False when we matched an existing guest card by phone or email
    message: str


class TourSlots(BaseModel):
    property_id: int
    property_name: str
    date: date
    timezone: str
    slot_minutes: int
    available_times: list[str]  # local times, "HH:MM" 24-hour, e.g. ["10:00", "10:30"]
    message: str


class TourConfirmation(BaseModel):
    tour_id: int
    guest_card_id: int
    property_name: str
    address: str
    starts_at_local: str  # e.g. "Saturday, 22 Nov 2026 at 11:00 AM IST"
    starts_at_utc: datetime
    duration_minutes: int
    leasing_office_phone: str
    rescheduled_from: str | None  # set when an earlier visit was moved to this time
    message: str