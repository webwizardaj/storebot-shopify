
import hmac
import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from shopify.cloudinary_client import CloudinaryClient
from shopify.dashboard_json import (
    load_dashboard_product_data_from_payload,
    get_product_cost,
)
from shopify.gemini_client import GeminiClient
from shopify.pricing import calculate_selling_price, MARKUP_PERCENT
from shopify.shopify_client import ShopifyClient
from shopify.shopify_products import (
    ProductCreatedButIncomplete,
    create_draft_product,
)

load_dotenv(override=True)

app = Flask(__name__)


def authorized():
    expected = os.getenv("STOREBOT_WEBHOOK_SECRET", "")
    supplied = request.headers.get("Authorization", "")

    if not expected:
        return False

    return hmac.compare_digest(
        supplied,
        f"Bearer {expected}"
    )


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "StoreBot Shopify",
        "status": "running",
        "pricing": f"Cost + {MARKUP_PERCENT}% markup",
        "product_status": "DRAFT"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/process", methods=["POST"])
def process_product():

    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Request must contain valid JSON."
        }), 400

    if payload.get("approved") is not True:
        return jsonify({
            "error": "Owner approval is required."
        }), 400

    dashboard_payload = payload.get("dashboard")

    if dashboard_payload is None:
        return jsonify({
            "error": "Dashboard JSON is missing."
        }), 400

    try:
        cloudinary = CloudinaryClient()
        gemini = GeminiClient()
        shopify = ShopifyClient()

        public_id = payload.get("public_id")

        if not public_id:
            return jsonify({
                "error": "Cloudinary public_id is required."
            }), 400

        image = cloudinary.get_image_details(public_id)

        if (
            "shopify_product_created" in image.get("tags", [])
            or image.get("context", {}).get("shopify_product_id")
        ):
            return jsonify({
                "error": "This image has already been processed."
            }), 409

        # Match dashboard JSON to the exact Cloudinary image
        dashboard_data = load_dashboard_product_data_from_payload(
            dashboard_payload,
            image
        )

        # Read actual product cost
        product_cost = get_product_cost(dashboard_data)

        # Automatically calculate cost + 40%
        selling_price = calculate_selling_price(product_cost)

        print("Product cost:", product_cost)
        print("Markup:", MARKUP_PERCENT, "%")
        print("Selling price:", selling_price)

        # Generate product content
        content = gemini.generate_product_content(
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
            "caption"
        ]

        for field in required_fields:
            if not content.get(field):
                raise ValueError(
                    f"Gemini response missing: {field}"
                )

        if not isinstance(content["tags"], list):
            raise ValueError("Invalid product tags.")

        product_data = {
            "title": content["title"],
            "description": content["description"],
            "price": str(selling_price),
            "vendor": dashboard_data.get("vendor", "StoreBot"),
            "product_type": dashboard_data.get(
                "product_type",
                "Accessories"
            ),
            "tags": content["tags"],
            "image_url": image["url"],
            "image_alt": content["title"]
        }

        # Create Shopify Draft product
        try:
            product = create_draft_product(
                shopify,
                product_data
            )

        except ProductCreatedButIncomplete as error:

            cloudinary.mark_as_processed(
                image["public_id"],
                error.product_id,
                status="created_price_update_failed"
            )

            return jsonify({
                "error": "Product created, but price update failed.",
                "product_id": error.product_id
            }), 502

        # Save Cloudinary tracking
        cloudinary.mark_as_processed(
            image["public_id"],
            product["id"],
            status="created"
        )

        return jsonify({
            "message": "Product created successfully.",
            "product_id": product["id"],
            "title": product["title"],
            "status": product["status"],
            "cost": str(product_cost),
            "markup_percent": str(MARKUP_PERCENT),
            "selling_price": str(selling_price)
        }), 201

    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("Product processing failed")

        return jsonify({
            "error": "Processing failed. Check Render logs."
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000"))
    )
