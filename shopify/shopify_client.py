
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()


class ShopifyClient:
    def __init__(self):
        self.store_domain = os.getenv("SHOPIFY_STORE_DOMAIN")
        self.client_id = os.getenv("SHOPIFY_CLIENT_ID")
        self.client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
        self.api_version = os.getenv(
            "SHOPIFY_API_VERSION", "2026-10"
        )

        if not all([
            self.store_domain,
            self.client_id,
            self.client_secret
        ]):
            raise ValueError("Missing Shopify credentials in .env")

        self.access_token = None
        self.token_expiry = 0

    def get_access_token(self):

        if (
            self.access_token
            and time.time() < self.token_expiry - 300
        ):
            return self.access_token

        url = (
            f"https://{self.store_domain}"
            "/admin/oauth/access_token"
        )

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        response = requests.post(
            url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Authentication failed: HTTP {response.status_code}"
                f"Shopify response: {response.text}"
            )

        data = response.json()

        self.access_token = data["access_token"]
        self.token_expiry = time.time() + data["expires_in"]

        print("Shopify authentication successful!")

        return self.access_token

    def graphql(self, query, variables=None):

        token = self.get_access_token()

        url = (
            f"https://{self.store_domain}"
            f"/admin/api/{self.api_version}/graphql.json"
        )

        response = requests.post(
            url,
            json={
                "query": query,
                "variables": variables or {}
            },
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": token
            },
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        if result.get("errors"):
            raise RuntimeError(
                f"GraphQL errors: {result['errors']}"
            )

        return result["data"]
