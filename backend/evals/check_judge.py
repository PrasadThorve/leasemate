import argparse
import asyncio
from datetime import datetime, timedelta

from app.agent.graph import IST, create_llm
from evals.judge import JUDGE_MODEL, make_judge

# Tool results shaped like the real MCP tool outputs (shortened).
AVAILABILITY = (
    '{"total_matches": 2, "matches": ['
    '{"unit_number": "A-502", "property_name": "Mulberry Heights", "floor_plan": "1 BHK", "rent": 14000, '
    '"rent_display": "₹14,000", "maintenance_display": "₹1,400", "security_deposit_display": "₹28,000", '
    '"available_on": "2026-11-28"}, '
    '{"unit_number": "B-303", "property_name": "Mulberry Heights", "floor_plan": "2 BHK", "rent": 23000, '
    '"rent_display": "₹23,000", "maintenance_display": "₹2,100", "security_deposit_display": "₹46,000", '
    '"available_on": "2026-12-05"}], "message": "Found 2 matching flats, cheapest first."}'
)
PROPERTY_DETAILS = (
    '{"property_id": 1, "name": "Mulberry Heights", "locality": "Hinjewadi", "phone": "+91 20 0000 1101", '
    '"description": "A gated community five minutes from Rajiv Gandhi Infotech Park Phase 1, with a free '
    'shuttle to the IT park.", "amenities": ["clubhouse", "gym", "swimming pool", "24x7 security with CCTV", '
    '"power backup", "IT park shuttle"], "pet_policy": "Pets are welcome. Keep pets on a leash in common '
    'areas and register them at the society office. No extra pet charges.", "parking": "One covered car '
    'parking with every 2 and 3 BHK; two-wheeler parking is free.", "security_deposit_months": 2, '
    '"site_visit_hours": "10:00 AM to 7:00 PM, every day"}'
)
TOMORROW = (datetime.now(IST) + timedelta(days=1)).date().isoformat()
TOUR_SLOTS = (
    f'{{"property_name": "Mulberry Heights", "date": "{TOMORROW}", "timezone": "Asia/Kolkata", '
    '"available_times": ["10:00", "10:30", "11:00", "11:30"], "message": "4 open times, each 30 minutes."}'
)
HANDOFF = (
    '{"handoff_id": 12, "status": "open", "contact_phone": "+91 20 0000 1101", "message": "Handoff #12 '
    'created. The leasing team will follow up. The person can also call +91 20 0000 1101."}'
)
RENT_REQUEST = "Can you reduce the rent to ₹20,000 for the 2 BHK at Mulberry Heights? I'll sign for 2 years."

CASES = [
    {
        "name": "correct price answer",
        "message": "Any 2 BHK at Mulberry Heights under ₹25,000?",
        "tools": {"check_availability": AVAILABILITY},
        "reply": "Yes! B-303 at Mulberry Heights is a 2 BHK for ₹23,000 a month, plus ₹2,100 maintenance "
        "and a ₹46,000 deposit. It's available from 5 December. Would you like to visit?",
        "expected": {"faithful": True, "answers_question": True, "policy": True},
    },
    {
        # prices_grounded PASSES this one (both amounts exist in the tool result). Only the judge can catch it.
        "name": "price attached to the wrong flat",
        "message": "How much is the 1 BHK at Mulberry Heights?",
        "tools": {"check_availability": AVAILABILITY},
        "reply": "The 1 BHK (A-502) at Mulberry Heights is ₹23,000 a month, with a ₹46,000 deposit.",
        "expected": {"faithful": False, "policy": True},
    },
    {
        "name": "wrong pet policy",
        "message": "Are pets allowed at Mulberry Heights? I have a Labrador.",
        "tools": {"get_property_details": PROPERTY_DETAILS},
        "reply": "Sorry, pets aren't allowed at Mulberry Heights.",
        "expected": {"faithful": False},
    },
    {
        "name": "invented amenities",
        "message": "What amenities does Mulberry Heights have?",
        "tools": {"get_property_details": PROPERTY_DETAILS},
        "reply": "Mulberry Heights has a clubhouse, gym, swimming pool, a tennis court and a rooftop cinema.",
        "expected": {"faithful": False, "answers_question": True},
    },
    {
        "name": "dodges the question",
        "message": "Is there parking for two cars at Mulberry Heights?",
        "tools": {"get_property_details": PROPERTY_DETAILS},
        "reply": "Mulberry Heights is a gated community with a clubhouse, gym and swimming pool. "
        "Would you like to see the available flats?",
        "expected": {"faithful": True, "answers_question": False},
    },
    {
        "name": "honestly says the information isn't available",
        "message": "Is there a good school near Mulberry Heights?",
        "tools": {"get_property_details": PROPERTY_DETAILS},
        "reply": "I don't have details about schools near Mulberry Heights. It's five minutes from Rajiv "
        "Gandhi Infotech Park Phase 1, and the leasing office on +91 20 0000 1101 can tell you more "
        "about the neighbourhood.",
        "expected": {"faithful": True, "answers_question": True, "policy": True},
    },
    {
        "name": "claims a booking that never happened",
        "message": "Please book a site visit at Mulberry Heights tomorrow at 11 AM.",
        "tools": {"get_tour_slots": TOUR_SLOTS},
        "reply": "Done! Your site visit at Mulberry Heights is booked for tomorrow at 11:00 AM.",
        "expected": {"faithful": False},
    },
    {
        "name": "correct handoff",
        "message": RENT_REQUEST,
        "tools": {"request_human_handoff": HANDOFF},
        "reply": "I can't change the rent myself, but I've passed your request to our leasing team "
        "(reference #12). They'll get back to you soon, or you can call them on +91 20 0000 1101.",
        "expected": {"faithful": True, "answers_question": True, "policy": True},
    },
    {
        "name": "promises a discount",
        "message": RENT_REQUEST,
        "tools": {"request_human_handoff": HANDOFF},
        "reply": "Good news: for a 2-year agreement we can usually do ₹20,000. I've passed this to the "
        "leasing team, who will follow up, or call them on +91 20 0000 1101.",
        "expected": {"policy": False},
    },
    {
        "name": "handoff without follow-up or phone number",
        "message": RENT_REQUEST,
        "tools": {"request_human_handoff": HANDOFF},
        "reply": "I've passed your request on.",
        "expected": {"faithful": True, "policy": False},
    },
    {
        "name": "too many questions at once",
        "message": "Any 2 BHK available?",
        "tools": {},
        "reply": "Happy to help! What's your budget? When do you want to move in? Furnished or unfurnished? "
        "Which area of Pune? Do you need car parking? Any pets?",
        "expected": {"faithful": True, "policy": False},
    },
]


async def grade(judge, case: dict) -> dict:
    outputs = {
        "reply": case["reply"],
        "guardrail": None,
        "tools_used": list(case["tools"]),
        "tool_outputs": list(case["tools"].values()),
    }
    result = await judge({"message": case["message"]}, outputs)
    return {
        "scores": {r["key"]: r["score"] for r in result["results"]},
        "reasoning": result["results"][0]["comment"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Check the LLM judge against replies with known verdicts.")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    args = parser.parse_args()

    judge = make_judge(create_llm(args.judge_model))
    print(f"Checking judge {args.judge_model} on {len(CASES)} replies...\n")
    graded = await asyncio.gather(*(grade(judge, case) for case in CASES))

    agreed = total = 0
    for case, result in zip(CASES, graded, strict=True):
        wrong = {key: value for key, value in case["expected"].items() if result["scores"][key] != value}
        total += len(case["expected"])
        agreed += len(case["expected"]) - len(wrong)

        print(f"{'✓' if not wrong else '✗'} {case['name']}")
        for key, expected in wrong.items():
            print(f"    {key}: expected {expected}, judge said {result['scores'][key]}")
        if wrong:
            print(f"    judge's reasoning: {result['reasoning']}")

    print(f"\nThe judge agreed on {agreed}/{total} checks.")
    if agreed < total:
        raise SystemExit("Don't trust the judge's scores yet: fix JUDGE_PROMPT in evals/judge.py and rerun.")
    print("The judge can be trusted on these cases.")


if __name__ == "__main__":
    asyncio.run(main())