from sqlalchemy import select

from db.database import SessionLocal
from db.models import Company, Handoff, Property


def main() -> None:
    with SessionLocal() as session:
        handoffs = session.scalars(select(Handoff).order_by(Handoff.created_at.desc())).all()
        if not handoffs:
            print("No handoffs yet.")
            return

        for handoff in handoffs:
            company = session.get(Company, handoff.company_id)
            prop = session.get(Property, handoff.property_id) if handoff.property_id else None
            where = prop.name if prop else "property not specified"
            print(f"#{handoff.id} [{handoff.status}] {handoff.reason} | {company.name} | {where}")
            print(f"    {handoff.summary}")
            print(f"    guest card: {handoff.guest_card_id or '-'} | created {handoff.created_at:%d %b %Y %H:%M} UTC\n")


if __name__ == "__main__":
    main()