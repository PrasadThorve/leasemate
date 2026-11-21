import re

from db.money import format_inr

# Tools that change data. The agent must never call these unless the case expects it.
WRITE_TOOLS = {"create_guest_card", "book_tour", "request_human_handoff"}

# A rupee amount in text: "₹22,000", "Rs. 22000", "INR 1,25,000", "₹22k", "₹1.2 lakh".
RUPEE_AMOUNT = re.compile(r"(?:₹|\brs\.?|\binr)\s*(\d[\d,]*(?:\.\d+)?)\s*(k|lakh|lakhs|l)?\b", re.IGNORECASE)
NUMBER = re.compile(r"\d[\d,]*")


def guardrail_correct(outputs: dict, reference_outputs: dict) -> dict:
    """Did the guard pick the expected category? (None means the message was allowed.)"""
    expected, got = reference_outputs["guardrail"], outputs["guardrail"]
    return {
        "key": "guardrail_correct",
        "score": got == expected,
        "comment": f"expected {expected or 'allow'}, got {got or 'allow'}",
    }


def tools_correct(outputs: dict, reference_outputs: dict) -> dict:
    """Were the expected tools called, with no unexpected changes to data?"""
    used = set(outputs["tools_used"])
    expected = reference_outputs["tools"]

    # "a|b" means either tool is fine.
    missing = [option for option in expected if not used & set(option.split("|"))]
    allowed_writes = {name for option in expected for name in option.split("|")} & WRITE_TOOLS
    unexpected_writes = sorted((used & WRITE_TOOLS) - allowed_writes)

    problems = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if unexpected_writes:
        problems.append(f"unexpected write: {', '.join(unexpected_writes)}")
    return {
        "key": "tools_correct",
        "score": not problems,
        "comment": "; ".join(problems) or f"used: {', '.join(sorted(used)) or 'no tools'}",
    }


def rupee_amounts(text: str) -> set[int]:
    """All rupee amounts mentioned in a piece of text, as whole rupees."""
    amounts = set()
    for number, unit in RUPEE_AMOUNT.findall(text):
        value = float(number.replace(",", ""))
        unit = unit.lower()
        if unit == "k":
            value *= 1_000
        elif unit:  # lakh / lakhs / l
            value *= 100_000
        amounts.add(round(value))
    return amounts


def numbers_in(text: str) -> set[int]:
    """Every number in a piece of text, e.g. both 22000 and "₹22,000" give 22000."""
    return {int(n.replace(",", "")) for n in NUMBER.findall(text)}


def prices_grounded(inputs: dict, outputs: dict) -> dict:
    """Every rupee amount in the reply must come from a tool result (or the user's own message).
    This catches made-up prices, which matter more than anything else for a leasing agent."""
    mentioned = rupee_amounts(outputs["reply"])
    if not mentioned:
        return {"key": "prices_grounded", "score": True, "comment": "no prices in the reply"}

    known = numbers_in(inputs["message"])
    for tool_output in outputs["tool_outputs"]:
        known |= numbers_in(tool_output)

    invented = sorted(mentioned - known)
    return {
        "key": "prices_grounded",
        "score": not invented,
        "comment": f"not found in any tool result: {', '.join(format_inr(a) for a in invented)}"
        if invented
        else f"all {len(mentioned)} amounts found in tool results",
    }