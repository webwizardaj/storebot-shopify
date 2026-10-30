
import json


COST_FIELDS = (
    "cost",
    "product_cost",
    "cost_price",
    "purchase_cost",
    "purchase_price",
    "base_cost",
    "unit_cost",
    "cost_price_inr",
    "product_cost_inr",
)


def get_product_cost(record):

    for key in COST_FIELDS:
        if record.get(key) is not None:
            return record[key]

    for key in ("pricing", "price_details", "cost_details"):
        nested = record.get(key)

        if isinstance(nested, dict):
            for cost_key in COST_FIELDS:
                if nested.get(cost_key) is not None:
                    return nested[cost_key]

    return None


def get_records(payload):

    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if not isinstance(payload, dict):
        raise ValueError("Invalid dashboard JSON.")

    for key in ("products", "items", "records"):
        if isinstance(payload.get(key), list):
            return payload[key]

    for key in ("product", "data", "result"):
        if isinstance(payload.get(key), dict):
            return [payload[key]]

    return [payload]


def matches_image(record, image):

    public_id = image.get("public_id")
    image_url = image.get("url")

    identifiers = [
        record.get("public_id"),
        record.get("cloudinary_public_id"),
        record.get("image_public_id"),
        record.get("image_url"),
        record.get("image"),
        record.get("url"),
    ]

    for identifier in identifiers:

        if not isinstance(identifier, str):
            continue

        identifier = identifier.strip()

        if identifier == public_id or identifier == image_url:
            return True

    return False


def load_dashboard_product_data_from_payload(payload, image):

    records = get_records(payload)

    matching = [
        record
        for record in records
        if matches_image(record, image)
    ]

    if len(matching) != 1:
        raise ValueError(
            "Dashboard JSON must contain exactly one product "
            "matching this Cloudinary image."
        )

    product = matching[0]

    if get_product_cost(product) is None:
        raise ValueError(
            "Product cost is missing from dashboard JSON."
        )

    return product
