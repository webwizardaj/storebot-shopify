
import os

import cloudinary
import cloudinary.api
import cloudinary.uploader

from dotenv import load_dotenv

load_dotenv(override=True)


class CloudinaryClient:

    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.api_key = os.getenv("CLOUDINARY_API_KEY")
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET")

        if not all([
            self.cloud_name,
            self.api_key,
            self.api_secret
        ]):
            raise ValueError(
                "Missing Cloudinary credentials in .env"
            )

        cloudinary.config(
            cloud_name=self.cloud_name,
            api_key=self.api_key,
            api_secret=self.api_secret,
            secure=True
        )

        self.processed_tag = "shopify_product_created"

    def fetch_images(self, limit=20):
        """
        Fetch newest uploaded images across the account.

        Skip images already processed by Shopify or
        images that already have a Shopify product ID.

        Supports pagination.
        """

        if limit < 1:
            raise ValueError("Limit must be at least 1.")

        images = []
        next_cursor = None

        while len(images) < limit:

            params = {
                "type": "upload",
                "resource_type": "image",
                "max_results": 500,
                "direction": "desc",
                "tags": True,
                "context": True
            }

            if next_cursor:
                params["next_cursor"] = next_cursor

            response = cloudinary.api.resources(**params)

            assets = response.get("resources", [])

            for asset in assets:

                tags = asset.get("tags", [])

                context = asset.get("context") or {}
                custom = context.get("custom", context)

                # Skip already processed images
                if self.processed_tag in tags:
                    continue

                # Skip images already linked to Shopify products
                if custom.get("shopify_product_id"):
                    continue

                images.append({
                    "public_id": asset["public_id"],
                    "url": asset["secure_url"],
                    "format": asset.get("format"),
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "tags": tags,
                    "context": custom,
                    "created_at": asset.get("created_at")
                })

                if len(images) >= limit:
                    break

            next_cursor = response.get("next_cursor")

            if not next_cursor:
                break

        return images

    def mark_as_processed(
        self,
        public_id,
        product_id,
        status="created"
    ):
        """
        Save Shopify product ID and status in Cloudinary.
        Add the Shopify processed tag.
        """

        if not public_id:
            raise ValueError("Cloudinary public_id is required.")

        if not product_id:
            raise ValueError("Shopify product_id is required.")

        if not status:
            raise ValueError("Processing status is required.")

        # Save Shopify product reference and status first
        context_response = cloudinary.api.update(
            public_id,
            context={
                "shopify_product_id": str(product_id),
                "shopify_status": str(status)
            },
            resource_type="image",
            type="upload"
        )

        # Add tracking tag
        tag_response = cloudinary.uploader.add_tag(
            self.processed_tag,
            [public_id],
            resource_type="image",
            type="upload"
        )

        if tag_response.get("failed"):
            raise RuntimeError(
                f"Cloudinary tagging failed: {tag_response['failed']}"
            )

        print("\nCloudinary tracking saved successfully.")
        print("Image:", public_id)
        print("Shopify Product ID:", product_id)
        print("Status:", status)

        return {
            "context": context_response,
            "tags": tag_response
        }

    def get_image_details(self, public_id):
        """
        Retrieve image details, tags and custom metadata.
        """

        result = cloudinary.api.resource(
            public_id,
            resource_type="image",
            type="upload",
            context=True
        )

        context = result.get("context") or {}
        custom = context.get("custom", context)

        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "format": result.get("format"),
            "width": result.get("width"),
            "height": result.get("height"),
            "tags": result.get("tags", []),
            "context": custom,
            "created_at": result.get("created_at")
        }
