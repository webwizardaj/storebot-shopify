
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MARKUP_PERCENT = Decimal("40")

MARKUP_MULTIPLIER = (
    Decimal("1") + MARKUP_PERCENT / Decimal("100")
)


def parse_cost(value):

    if value is None or isinstance(value, bool):
        raise ValueError("Product cost is missing or invalid.")

    cleaned = (
        str(value)
        .replace("₹", "")
        .replace("INR", "")
        .replace(",", "")
        .strip()
    )

    try:
        cost = Decimal(cleaned)

    except (InvalidOperation, ValueError):
        raise ValueError("Invalid product cost.")

    if not cost.is_finite() or cost <= 0:
        raise ValueError("Cost must be greater than zero.")

    return cost


def calculate_selling_price(cost):

    cost = parse_cost(cost)

    selling_price = cost * MARKUP_MULTIPLIER

    return selling_price.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
