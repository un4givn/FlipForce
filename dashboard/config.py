# dashboard/config.py
import os

from dotenv import load_dotenv

# Load environment variables from .env file.
# This ensures that when this module is imported,
# the environment variables are available for DB_CONFIG.
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("FLIPFORCE_POSTGRES_HOST", "flipforce-db"),
    "port": int(os.getenv("FLIPFORCE_POSTGRES_PORT", 5432)),
    "dbname": os.getenv("FLIPFORCE_POSTGRES_DB"),
    "user": os.getenv("FLIPFORCE_POSTGRES_USER"),
    "password": os.getenv("FLIPFORCE_POSTGRES_PASSWORD"),
}

PACK_CATEGORY_ORDER = [
    "Diamond",
    "Emerald",
    "Ruby",
    "Gold",
    "Silver",
    "Misc.",
    "Misc",
    "Unknown Category",
]
STATIC_PACK_COSTS_CENTS = {
    "Diamond": 100000,
    "Emerald": 50000,
    "Ruby": 25000,
    "Gold": 10000,
    "Silver": 5000,
    "Misc.": 2500,
    "Misc": 2500,
}
