
from decimal import Decimal, InvalidOperation


class ProductCreatedButIncomplete(Exception):
    """Shopify created the product, but a later step failed."""

    def __init__(self, product_id, message):
        self.product_id = product_id
        super().__init__(message)


def create_draft_product(client, product_data):
    """
    Create one Shopify Draft product with an image and validated selling price.

    Required:
        title, description, price, image_url

    Optional:
        vendor, product_type, tags, image_alt
    """

    title = str(product_data.get("title", "")).strip()
    description = str(product_data.get("description", "")).strip()
    image_url = str(product_data.get("image_url", "")).strip()

    if not title:
        raise ValueError("Product title is required.")

    if not description:
        raise ValueError("Product description is required.")

    if not image_url.startswith("https://"):
        raise ValueError("A valid HTTPS product image URL is required.")

    try:
        price = Decimal(str(product_data["price"]))
    except (KeyError, InvalidOperation, ValueError):
        raise ValueError("Enter a valid product price.")

    if not price.is_finite() or price <= 0:
        raise ValueError("Product price must be greater than zero.")

    tags = product_data.get("tags", [])

    if not isinstance(tags, list):
        raise ValueError("Product tags must be a list.")

    tags = list(dict.fromkeys(
        str(tag).strip() for tag in tags if str(tag).strip()
    ))

    product_input = {
        "title": title,
        "descriptionHtml": description,
        "status": "DRAFT",
        "vendor": product_data.get("vendor", "StoreBot"),
        "productType": product_data.get("product_type", ""),
        "tags": tags
    }

    media = [{
        "originalSource": image_url,
        "alt": product_data.get("image_alt", title),
        "mediaContentType": "IMAGE"
    }]

    create_mutation = """
    mutation CreateDraftProduct(
        $product: ProductCreateInput!,
        $media: [CreateMediaInput!]
    ) {
        productCreate(product: $product, media: $media) {
            product {
                id
                title
                status
                variants(first: 1) {
                    nodes {
                        id
                        price
                    }
                }
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    result = client.graphql(
        create_mutation,
        {
            "product": product_input,
            "media": media
        }
    )

    payload = result["productCreate"]

    if payload["userErrors"]:
        raise RuntimeError(
            f"Shopify product creation failed: {payload['userErrors']}"
        )

    product = payload.get("product")

    if not product:
        raise RuntimeError(
            "Shopify did not return a product after creation."
        )

    product_id = product["id"]
    variants = product.get("variants", {}).get("nodes", [])

    if not variants:
        raise ProductCreatedButIncomplete(
            product_id,
            "Product was created, but its initial variant was not returned."
        )

    price_mutation = """
    mutation UpdateProductPrice(
        $productId: ID!,
        $variants: [ProductVariantsBulkInput!]!
    ) {
        productVariantsBulkUpdate(
            productId: $productId,
            variants: $variants
        ) {
            productVariants {
                id
                price
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    try:
        price_result = client.graphql(
            price_mutation,
            {
                "productId": product_id,
                "variants": [{
                    "id": variants[0]["id"],
                    "price": str(price)
                }]
            }
        )

        price_payload = price_result["productVariantsBulkUpdate"]

        if price_payload["userErrors"]:
            raise RuntimeError(str(price_payload["userErrors"]))

        updated_variants = price_payload.get("productVariants", [])

        if not updated_variants:
            raise RuntimeError("Shopify returned no updated variant.")

    except Exception as exc:
        raise ProductCreatedButIncomplete(
            product_id,
            f"Product exists as Draft, but price update failed. "
            f"Product ID: {product_id}. Error: {exc}"
        ) from exc

    print("\nShopify Draft product created successfully!")
    print("Title:", product["title"])
    print("Product ID:", product_id)
    print("Status:", product["status"])
    print("Price:", updated_variants[0]["price"])

    return {
        "id": product_id,
        "title": product["title"],
        "status": product["status"],
        "price": updated_variants[0]["price"]
    }
