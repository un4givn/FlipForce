import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
# This path might need adjustment if .env is not found relative to where tracker.py runs
# However, Docker's env_file in docker-compose usually handles making them available directly.
load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("TRACKER_POSTGRES_DB"),
        user=os.getenv("TRACKER_POSTGRES_USER"),
        password=os.getenv("TRACKER_POSTGRES_PASSWORD"),
        host=os.getenv("TRACKER_POSTGRES_HOST"), # Should be 'flipforce-db'
        port=os.getenv("TRACKER_POSTGRES_PORT", 5432) # Should be 5432
    )