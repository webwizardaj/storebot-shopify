
from decimal import Decimal, InvalidOperation

from shopify.cloudinary_client import CloudinaryClient
from shopify.gemini_client import GeminiClient
from shopify.shopify_client import ShopifyClient
from shopify.shopify_products import (
    create_draft_product,
    ProductCreatedButIncomplete,
)


def get_product_price():
    while True:
        value = input("\nEnter product selling price (INR): ").strip()

        try:
            price = Decimal(value)

            if price.is_finite() and price > 0:
                return price

            print("Price must be greater than zero.")

        except InvalidOperation:
            print("Invalid price. Please enter a valid number.")


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

    # Fetch the newest unprocessed image
    images = cloudinary_client.fetch_images(limit=1)

    if not images:
        print("No unprocessed images found in Cloudinary.")
        return

    image = images[0]

    print("\nSelected image:", image["public_id"])
    print("Image URL:", image["url"])

    # Generate product content
    print("\nGenerating product content with Gemini...")

    content = gemini_client.generate_product_content(
        image_url=image["url"],
        extra_details=(
            "Generate truthful product content. "
            "Do not assume brand, material, fabric, "
            "authenticity, size, or specifications "
            "unless independently provided. "
            "Do not invent product features."
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

    print("\n--- GENERATED PRODUCT CONTENT ---")
    print("Title:", content["title"])
    print("Description:", content["description"])
    print("Tags:", content["tags"])
    print("SEO title:", content["seo_title"])
    print("SEO description:", content["seo_description"])
    print("Caption:", content["caption"])

    # Manual pricing
    price = get_product_price()

    # Final confirmation
    print("\n--- PRODUCT CREATION REVIEW ---")
    print("Title:", content["title"])
    print("Price: ₹", price)
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
        "price": str(price),
        "vendor": "StoreBot",
        "product_type": "Accessories",
        "tags": content["tags"],
        "image_url": image["url"],
        "image_alt": content["title"],
    }

    # Create Shopify Draft product
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

    # Track successful product creation
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

