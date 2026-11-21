
def format_inr(amount: int | float) -> str:
    """Format a rupee amount the Indian way, e.g. 125000 -> '₹1,25,000'."""
    sign = "-" if amount < 0 else ""
    digits = str(abs(round(amount)))

    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])

    return f"{sign}₹{digits}"