"""Calls every MCP tool once, like the agent will, and prints the results.

Run from the backend folder (no need to start the server first):
    uv run python -m scripts.try_mcp_tools

It uses FastMCP's in-memory client, which talks to the server object directly
instead of over HTTP. Note: it really books a visit in your database. Run
`uv run python -m db.seed` any time to reset.
"""
import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastmcp import Client
from fastmcp.exceptions import ToolError

# Act as company 1 (Sahyadri). In the real app the backend sends this as a header.
os.environ.setdefault("DEFAULT_COMPANY_ID", "1")

from mcp_server.server import mcp  # noqa: E402


def show(title: str, data) -> None:
    print(f"\n--- {title} ---")
    print(data)


async def main() -> None:
    tomorrow = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date()

    async with Client(mcp) as client:
        tools = await client.list_tools()
        show("Tools", [tool.name for tool in tools])

        result = await client.call_tool("list_properties", {})
        for prop in result.structured_content["result"]:
            plans = ", ".join(f"{p['floor_plan']} from {p['rent_from_display']}" for p in prop["floor_plans"])
            show(f"Property {prop['property_id']}: {prop['name']} ({prop['locality']})", plans)

        result = await client.call_tool("get_property_details", {"property_id": 1})
        details = result.structured_content
        show("Details of property 1", f"{details['site_visit_hours']} | Pets: {details['pet_policy'][:60]}...")

        result = await client.call_tool(
            "check_availability", {"bedrooms": 2, "max_rent": 30000, "limit": 3}
        )
        availability = result.structured_content
        show("2 BHK under ₹30,000", availability["message"])
        for unit in availability["matches"]:
            print(
                f"  {unit['property_name']} {unit['unit_number']}: {unit['rent_display']}/month "
                f"+ {unit['maintenance_display']} maintenance, deposit {unit['security_deposit_display']}, "
                f"{unit['furnishing']}, available {unit['available_on']}"
            )

        result = await client.call_tool("check_availability", {"bedrooms": 3, "max_rent": 20000})
        show("3 BHK under ₹20,000 (should find nothing, with a hint)", result.structured_content["message"])

        result = await client.call_tool(
            "create_guest_card",
            {
                "property_id": 1,
                "first_name": "Aarav",
                "last_name": "Kulkarni",
                "phone": "98765 43210",
                "desired_bedrooms": 2,
                "max_budget": 30000,
                "pets": "one dog",
            },
        )
        card = result.structured_content
        show("Guest card", card)

        result = await client.call_tool(
            "get_tour_slots", {"property_id": 1, "visit_date": tomorrow.isoformat()}
        )
        slots = result.structured_content
        show(f"Open times on {tomorrow}", slots["available_times"])

        first, second = slots["available_times"][0], slots["available_times"][2]
        booking = {"property_id": 1, "guest_card_id": card["guest_card_id"], "visit_date": tomorrow.isoformat()}

        result = await client.call_tool("book_tour", {**booking, "start_time": first})
        show("Booked", result.structured_content["message"])

        result = await client.call_tool("book_tour", {**booking, "start_time": second})
        show("Rescheduled", result.structured_content["message"])

        print("\n--- Tenant isolation: company 1 asks for property 4 (belongs to company 2) ---")
        try:
            await client.call_tool("get_property_details", {"property_id": 4})
        except ToolError as error:
            print(f"Blocked as expected: {error}")

        print("\n--- Bad phone number ---")
        try:
            await client.call_tool(
                "create_guest_card",
                {"property_id": 1, "first_name": "Test", "last_name": "User", "phone": "12345"},
            )
        except ToolError as error:
            print(f"Rejected as expected: {error}")


if __name__ == "__main__":
    asyncio.run(main())