import json

from shopify.cloudinary_client import CloudinaryClient
from shopify.gemini_client import GeminiClient
from shopify.shopify_client import ShopifyClient
from shopify.shopify_products import (
    create_draft_product,
    ProductCreatedButIncomplete,
)
from shopify.dashboard_json import (
    load_dashboard_product_data,
    get_product_cost,
)
from shopify.pricing import calculate_selling_price, MARKUP_PERCENT


def save_cloudinary_tracking(
    cloudinary_client,
    public_id,
    product_id,
    status
):
    try:
        cloudinary_client.mark_as_processed(
            public_id,
            product_id,
            status=status
        )
        return True

    except Exception as error:
        print("\nWARNING: Shopify product exists, but Cloudinary tracking failed.")
        print("Product ID:", product_id)
        print("Tracking error:", error)
        print("Do not rerun this image until tracking is repaired.")
        return False


def main():
    cloudinary_client = CloudinaryClient()
    gemini_client = GeminiClient()
    shopify_client = ShopifyClient()

    # Fetch the newest unprocessed image from Cloudinary.
    images = cloudinary_client.fetch_images(limit=1)

    if not images:
        print("No unprocessed images found in Cloudinary.")
        return

    image = images[0]

    print("\nSelected image:", image["public_id"])
    print("Image URL:", image["url"])

    # Read the corresponding product information and cost from dashboard JSON.
    try:
        dashboard_data = load_dashboard_product_data(image)
        product_cost = get_product_cost(dashboard_data)
        selling_price = calculate_selling_price(product_cost)
    except Exception as error:
        print("\nAutomatic pricing could not continue:", error)
        print("No Shopify product was created.")
        return

    print("\n--- AUTOMATIC PRICING ---")
    print(f"Product cost: ₹{product_cost}")
    print(f"Markup: {MARKUP_PERCENT}%")
    print(f"Calculated selling price: ₹{selling_price}")

    # Pass dashboard details to Gemini so it can use supplied product facts.
    print("\nGenerating product content with Gemini...")

    content = gemini_client.generate_product_content(
        image_url=image["url"],
        extra_details=json.dumps(
            dashboard_data,
            ensure_ascii=False,
            default=str
        )
    )

    required_fields = [
        "title",
        "description",
        "tags",
        "seo_title",
        "seo_description",
        "caption",
    ]

    for field in required_fields:
        if field not in content or content[field] is None:
            raise ValueError(
                f"Gemini response is missing required field: {field}"
            )

    if not isinstance(content["tags"], list):
        raise ValueError("Gemini returned invalid product tags.")

    print("\n--- GENERATED PRODUCT CONTENT ---")
    print("Title:", content["title"])
    print("Description:", content["description"])
    print("Tags:", content["tags"])
    print("SEO title:", content["seo_title"])
    print("SEO description:", content["seo_description"])
    print("Caption:", content["caption"])

    # Keep the existing human approval step; price itself is fully automatic.
    print("\n--- PRODUCT CREATION REVIEW ---")
    print("Title:", content["title"])
    print(f"Cost: ₹{product_cost}")
    print(f"Markup: {MARKUP_PERCENT}%")
    print(f"Selling price: ₹{selling_price}")
    print("Status: DRAFT")

    confirmation = input(
        "\nCreate this Draft product in Shopify? (yes/no): "
    ).strip().lower()

    if confirmation != "yes":
        print("Product creation cancelled.")
        return

    product_data = {
        "title": content["title"],
        "description": content["description"],
        "price": str(selling_price),
        "vendor": dashboard_data.get("vendor", "StoreBot"),
        "product_type": dashboard_data.get("product_type", "Accessories"),
        "tags": content["tags"],
        "image_url": image["url"],
        "image_alt": content["title"],
    }

    # Create Shopify Draft product using the automatically calculated price.
    try:
        product = create_draft_product(
            shopify_client,
            product_data
        )

    except ProductCreatedButIncomplete as error:
        print("\nWARNING: Product was created, but a later step failed.")
        print("Shopify Product ID:", error.product_id)

        save_cloudinary_tracking(
            cloudinary_client,
            image["public_id"],
            error.product_id,
            status="created_price_update_failed"
        )

        print("Please inspect the Draft product in Shopify Admin.")
        return

    except Exception as error:
        print("\nProduct creation failed:", error)
        print("Check Shopify Admin before attempting another run.")
        return

    print("\nShopify product created successfully!")
    print("Product ID:", product["id"])
    print("Title:", product["title"])
    print("Status:", product["status"])
    print("Price:", product["price"])

    tracking_saved = save_cloudinary_tracking(
        cloudinary_client,
        image["public_id"],
        product["id"],
        status="created"
    )

    if tracking_saved:
        print("\nAutomation completed successfully!")
    else:
        print("\nProduct created, but tracking needs manual repair.")


if __name__ == "__main__":
    main()

