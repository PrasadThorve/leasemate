"""Creates the database and fills it with fake (but realistic) Pune rental data.

Run from the backend folder:
    uv run python -m db.seed

Running it again deletes everything and starts fresh.

Rents are based on 2026 market ranges for each locality (unfurnished base rent,
plus premiums for higher floors and furnishing). All company names, property
names, addresses, phone numbers and emails are made up.
"""
import random
from datetime import date, timedelta

from db.database import SessionLocal, init_db
from db.models import Company, Property, Unit

# A fixed seed gives the same "random" units every run, so demos and tests are repeatable.
rng = random.Random(42)

# Availability dates are relative to today, so the demo always has open flats
# no matter which day you run it.
AVAILABILITY_OFFSETS_DAYS = [0, 0, 7, 15, 30, 45, 60]

# (furnishing, chance, rent multiplier)
FURNISHING_OPTIONS = [
    ("unfurnished", 0.5, 1.00),
    ("semi-furnished", 0.35, 1.08),
    ("fully furnished", 0.15, 1.20),
]

UNIT_FEATURES = [
    "modular kitchen",
    "piped gas connection",
    "attached balcony",
    "dry balcony",
    "east-facing",
    "wardrobes in all bedrooms",
    "geysers in bathrooms",
    "park view",
    "corner flat",
]

# AWBI (Animal Welfare Board of India) guidelines say housing societies cannot ban pets,
# so every property allows them, with the usual reasonable society rules.
PET_POLICY = (
    "Pets are welcome. As per Animal Welfare Board of India (AWBI) guidelines, housing "
    "societies cannot ban pets. Society rules: keep pets on a leash in common areas, clean "
    "up after them, and register them at the society office. No extra pet charges."
)

# Rental agreements in Pune are leave and licence agreements under the Maharashtra
# Rent Control Act, and registration is mandatory.
AGREEMENT_NOTES = (
    "11-month leave and licence agreement, registered online with the Maharashtra "
    "government (stamp duty and registration charges are split equally). Police "
    "verification of all adult occupants is required before move-in."
)

ASIA_KOLKATA = "Asia/Kolkata"
EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]
MON_TO_SAT = [0, 1, 2, 3, 4, 5]

# Floor plan tuples:
# (name, bedrooms, bathrooms, carpet area sqft, unfurnished base rent INR, number of units)
COMPANIES = [
    {
        "name": "Sahyadri Rental Communities",
        "properties": [
            {
                "name": "Mulberry Heights",
                "address": "Survey No. 112, Phase 1, Hinjewadi, Pune 411057",
                "locality": "Hinjewadi",
                "pincode": "411057",
                "phone": "+91 20 0000 1101",
                "email": "leasing@mulberryheights.example",
                "description": (
                    "A gated community five minutes from Rajiv Gandhi Infotech Park Phase 1, "
                    "popular with IT professionals, with a free shuttle to the IT park."
                ),
                "amenities": [
                    "clubhouse",
                    "gym",
                    "swimming pool",
                    "24x7 security with CCTV",
                    "power backup",
                    "IT park shuttle",
                ],
                "parking": "One covered car parking with every 2 and 3 BHK; two-wheeler parking is free.",
                "current_offer": "Zero brokerage: rent directly from us.",
                "security_deposit_months": 2,
                "lock_in_months": 6,
                "notice_period_days": 30,
                "tour_days": EVERY_DAY,
                "tour_start_hour": 10,
                "tour_end_hour": 19,
                "maintenance_per_sqft": 3.0,
                "floors": 14,
                "wings": ["A", "B"],
                "floor_plans": [
                    ("1 RK", 0, 1.0, 320, 9500, 3),
                    ("1 BHK", 1, 1.0, 480, 13500, 4),
                    ("2 BHK", 2, 2.0, 690, 22000, 4),
                    ("3 BHK", 3, 3.0, 980, 32000, 2),
                ],
            },
            {
                "name": "Riverstone Residences",
                "address": "Plot 18, Kharadi-Hadapsar Bypass Road, Kharadi, Pune 411014",
                "locality": "Kharadi",
                "pincode": "411014",
                "phone": "+91 20 0000 1102",
                "email": "hello@riverstone.example",
                "description": (
                    "Modern towers close to EON IT Park and the World Trade Center in Kharadi, "
                    "a short drive from Phoenix Marketcity and the airport."
                ),
                "amenities": [
                    "clubhouse",
                    "gym",
                    "swimming pool",
                    "co-working lounge",
                    "kids' play area",
                    "EV charging",
                ],
                "parking": "One covered car parking per flat; a second slot is ₹1,500/month if available.",
                "current_offer": "First month's maintenance waived for move-ins within 30 days.",
                "security_deposit_months": 3,
                "lock_in_months": 6,
                "notice_period_days": 30,
                "tour_days": EVERY_DAY,
                "tour_start_hour": 10,
                "tour_end_hour": 19,
                "maintenance_per_sqft": 3.5,
                "floors": 18,
                "wings": ["A", "B", "C"],
                "floor_plans": [
                    ("1 BHK", 1, 1.0, 500, 15000, 4),
                    ("2 BHK", 2, 2.0, 720, 26000, 4),
                    ("3 BHK", 3, 3.0, 1050, 35000, 3),
                ],
            },
            {
                "name": "Banyan Court",
                "address": "Sr. No. 45, Baner-Balewadi Road, Baner, Pune 411045",
                "locality": "Baner",
                "pincode": "411045",
                "phone": "+91 20 0000 1103",
                "email": "leasing@banyancourt.example",
                "description": (
                    "A quiet, premium community on Baner-Balewadi Road, close to Balewadi "
                    "High Street and the Mumbai-Bengaluru highway."
                ),
                "amenities": [
                    "clubhouse",
                    "gym",
                    "swimming pool",
                    "jogging track",
                    "24x7 security with CCTV",
                    "power backup",
                ],
                "parking": "One covered car parking with every flat; visitor parking available.",
                "current_offer": None,
                "security_deposit_months": 3,
                "lock_in_months": 11,
                "notice_period_days": 30,
                "tour_days": EVERY_DAY,
                "tour_start_hour": 10,
                "tour_end_hour": 19,
                "maintenance_per_sqft": 4.0,
                "floors": 12,
                "wings": ["A", "B"],
                "floor_plans": [
                    ("1 BHK", 1, 1.0, 520, 18000, 3),
                    ("2 BHK", 2, 2.0, 760, 32000, 4),
                    ("3 BHK", 3, 3.0, 1120, 42000, 3),
                ],
            },
        ],
    },
    {
        # A second, separate company. It exists so we can later prove tenant
        # isolation: Sahyadri's agent must never see Indrayani's data.
        "name": "Indrayani Homes",
        "properties": [
            {
                "name": "Lotus Court",
                "address": "Lane 7, Koregaon Park, Pune 411001",
                "locality": "Koregaon Park",
                "pincode": "411001",
                "phone": "+91 20 0000 2201",
                "email": "lotuscourt@indrayani.example",
                "description": "Low-rise luxury apartments on a leafy lane in Koregaon Park.",
                "amenities": ["landscaped garden", "gym", "24x7 security with CCTV", "power backup"],
                "parking": "Two covered car parkings with every flat.",
                "current_offer": None,
                "security_deposit_months": 3,
                "lock_in_months": 11,
                "notice_period_days": 60,
                "tour_days": MON_TO_SAT,
                "tour_start_hour": 10,
                "tour_end_hour": 18,
                "maintenance_per_sqft": 5.0,
                "floors": 5,
                "wings": ["A"],
                "floor_plans": [
                    ("2 BHK", 2, 2.0, 850, 48000, 3),
                    ("3 BHK", 3, 3.0, 1250, 72000, 2),
                ],
            },
        ],
    },
]

# Keys in the property dicts above that are seed settings, not database columns.
SEED_ONLY_KEYS = {"floor_plans", "maintenance_per_sqft", "floors", "wings"}


def round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def pick_furnishing() -> tuple[str, float]:
    roll = rng.random()
    cumulative = 0.0
    for name, chance, multiplier in FURNISHING_OPTIONS:
        cumulative += chance
        if roll < cumulative:
            return name, multiplier
    return FURNISHING_OPTIONS[0][0], FURNISHING_OPTIONS[0][2]


def build_units(property_data: dict, today: date) -> list[Unit]:
    """Generate flats for one property from its floor plans."""
    units: list[Unit] = []
    used_numbers: set[str] = set()

    for plan_name, bedrooms, bathrooms, area, base_rent, count in property_data["floor_plans"]:
        for _ in range(count):
            # Pick a wing and floor, and a flat number that isn't taken yet, e.g. "B-1204".
            while True:
                wing = rng.choice(property_data["wings"])
                floor = rng.randint(1, property_data["floors"])
                unit_number = f"{wing}-{floor}{rng.randint(1, 4):02d}"
                if unit_number not in used_numbers:
                    used_numbers.add(unit_number)
                    break

            carpet_area = area + rng.choice([-20, 0, 0, 15, 30])
            furnishing, multiplier = pick_furnishing()
            # Higher floors cost a little more (1% per floor), plus furnishing and some variation.
            floor_premium = 1 + (floor - 1) * 0.01
            rent = (base_rent * floor_premium + rng.choice([0, 0, 500])) * multiplier

            units.append(
                Unit(
                    unit_number=unit_number,
                    floor_plan=plan_name,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    carpet_area_sqft=carpet_area,
                    floor=floor,
                    furnishing=furnishing,
                    rent=round_to(rent, 500),
                    maintenance=round_to(carpet_area * property_data["maintenance_per_sqft"], 100),
                    available_on=today + timedelta(days=rng.choice(AVAILABILITY_OFFSETS_DAYS)),
                    status="leased" if rng.random() < 0.15 else "available",
                    features=rng.sample(UNIT_FEATURES, k=rng.randint(2, 3)),
                )
            )
    return units


def seed() -> None:
    init_db(drop_existing=True)
    today = date.today()

    with SessionLocal() as session:
        for company_data in COMPANIES:
            company = Company(name=company_data["name"])

            for property_data in company_data["properties"]:
                columns = {k: v for k, v in property_data.items() if k not in SEED_ONLY_KEYS}
                prop = Property(
                    **columns,
                    city="Pune",
                    state="Maharashtra",
                    timezone=ASIA_KOLKATA,
                    pet_policy=PET_POLICY,
                    agreement_notes=AGREEMENT_NOTES,
                )
                prop.units = build_units(property_data, today)
                company.properties.append(prop)

            session.add(company)

        session.commit()

        total_units = session.query(Unit).count()
        available = session.query(Unit).filter(Unit.status == "available").count()
        print(
            f"Seeded {session.query(Company).count()} companies, "
            f"{session.query(Property).count()} properties, "
            f"{total_units} flats ({available} available)."
        )


if __name__ == "__main__":
    seed()