
import os
import json
import time

from google import genai
from google.genai import types
from google.genai import errors
from dotenv import load_dotenv

load_dotenv(override=True)


class GeminiClient:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY missing from .env")

        self.client = genai.Client(api_key=api_key)

        # Primary model and fallback model
        self.models = [
            "gemini-3.8-flash"
        ]

        self.max_retries = 5

    def _generate_with_retry(self, model, prompt, image_url):

        for attempt in range(self.max_retries):
            try:
                print(
                    f"Using {model} "
                    f"(attempt {attempt + 1}/{self.max_retries})..."
                )

                response = self.client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        types.Part.from_uri(
                            file_uri=image_url,
                            mime_type="image/jpeg"
                        )
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.4
                    )
                )

                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")

                return json.loads(response.text)

            except errors.APIError as exc:

                status_code = getattr(exc, "code", None)

                # Retry temporary server and rate-limit errors
                if status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** (attempt + 1)

                        print(
                            f"Gemini temporarily unavailable. "
                            f"Retrying in {wait_time} seconds..."
                        )

                        time.sleep(wait_time)
                        continue

                raise

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Gemini returned invalid JSON."
                ) from exc

        raise RuntimeError(f"All retries failed for {model}.")

    def generate_product_content(self, image_url, extra_details=None):

        prompt = f"""
        You are an expert e-commerce product copywriter.

        Analyze the supplied product image and generate
        professional Shopify product content.

        Additional product information:
        {extra_details or "No additional information provided."}

        Return ONLY valid JSON with these fields:

        {{
            "title": "SEO-friendly product title",
            "description": "Attractive HTML product description",
            "tags": ["tag1", "tag2", "tag3"],
            "seo_title": "SEO title",
            "seo_description": "SEO meta description",
            "caption": "Marketing caption"
        }}

        Rules:
        - Describe only visible and verified characteristics.
        - Never invent fabric, material, brand, sizes or specifications.
        - Do not invent prices.
        - Keep the title concise and professional.
        - Make the description persuasive but truthful.
        - Return valid JSON only.
        """

        last_error = None

        for model in self.models:
            try:
                return self._generate_with_retry(
                    model=model,
                    prompt=prompt,
                    image_url=image_url
                )

            except Exception as exc:
                last_error = exc

                print(f"\nModel {model} failed: {exc}")
                print("Trying the next configured model...")

        raise RuntimeError(
            f"All configured Gemini models failed. "
            f"Last error: {last_error}"
        )
