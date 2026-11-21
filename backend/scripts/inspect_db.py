"""Prints a quick summary of what's in the database.

Run from the backend folder:
    uv run python -m scripts.inspect_db
"""
from sqlalchemy import func, select

from db.database import SessionLocal
from db.models import Company, Property, Unit
from db.money import format_inr


def main() -> None:
    with SessionLocal() as session:
        companies = session.scalars(select(Company).order_by(Company.id)).all()

        for company in companies:
            print(f"\n=== {company.name} (company {company.id}) ===")

            for prop in company.properties:
                print(f"\n{prop.name} - {prop.locality}, {prop.city} {prop.pincode}")
                print(f"  Deposit: {prop.security_deposit_months} months' rent | "
                      f"Lock-in: {prop.lock_in_months} months")
                if prop.current_offer:
                    print(f"  Offer: {prop.current_offer}")

                rows = session.execute(
                    select(
                        Unit.floor_plan,
                        func.count(),
                        func.min(Unit.rent),
                        func.max(Unit.rent),
                        func.min(Unit.available_on),
                    )
                    .where(Unit.property_id == prop.id, Unit.status == "available")
                    .group_by(Unit.bedrooms, Unit.floor_plan)
                    .order_by(Unit.bedrooms)
                ).all()

                for plan, count, min_rent, max_rent, earliest in rows:
                    print(
                        f"  {plan:<6} {count} available, {format_inr(min_rent)}-"
                        f"{format_inr(max_rent)}/month, earliest {earliest}"
                    )

        total = session.scalar(select(func.count()).select_from(Property))
        print(f"\n{total} properties in total.")


if __name__ == "__main__":
    main()