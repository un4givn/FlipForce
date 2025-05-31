# dashboard/config.py
import os

from dotenv import load_dotenv

# Load environment variables from .env file.
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

# Static pack costs, ensure keys match exactly what's in your DB or API responses
STATIC_PACK_COSTS_CENTS = {
    "Diamond": 100000,
    "Emerald": 50000,
    "Ruby": 25000,
    "Gold": 10000,
    "Silver": 5000,
    "Misc.": 2500,
    "Misc": 2500,
}

# Color definitions for the dashboard
# Updated with colors based on your SnatchR Color_Usage_by_UI_Component.csv and standard Tailwind hex values
COLORS = {
    "background": "#111827",          # Tailwind gray-900 (from SnatchR index.css & common dark bg)
    "card_background": "#1F2937",     # Tailwind gray-800 (from SnatchR CSV & index.css scrollbar)
    "text": "#F3F4F6",                # Tailwind gray-100 (from SnatchR CSV for Text/Title)
    "primary": "#9333EA",            # Tailwind purple-600 (from SnatchR CSV for Button/Text)
    "secondary": "#6B7280",          # Tailwind gray-500 (from SnatchR CSV & index.css scrollbar)
    "border_color": "#4B5563",       # Tailwind gray-600 (from SnatchR CSV & index.css scrollbar)
    
    "positive_roi_fg": "#FFFFFF",     # White text on colored background
    "positive_roi_bg": "#16A34A",     # Tailwind green-600 (from SnatchR CSV for Button/Text)
    "warning_roi_fg": "#FFFFFF",      # White text on yellow background for better contrast with darker yellow
    "warning_roi_bg": "#CA8A04",     # Tailwind yellow-600 (from SnatchR CSV for Alert/Text)
    "negative_roi_fg": "#FFFFFF",     # White text on red background
    "negative_roi_bg": "#DC2626",     # Tailwind red-600 (from SnatchR CSV for Button/Stat/Text)
    
    "link_color": "#60A5FA",          # Tailwind blue-400 (from SnatchR CSV for Text/Title)
}

# ROI display thresholds
ROI_THRESHOLDS = {
    "positive": 0.0,  # Greater than 0% is positive
    "warning": -0.03  # Between -3% and 0% is warning
}
