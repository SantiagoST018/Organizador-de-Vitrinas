import os

from dotenv import load_dotenv


load_dotenv()


SHOPIFY_SHOP = os.getenv("SHOPIFY_SHOP")

SHOPIFY_API_VERSION = os.getenv(
    "SHOPIFY_API_VERSION",
    "2026-10"
)

SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")

SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")