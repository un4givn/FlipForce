import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file.
# In a Docker environment managed by docker-compose with 'env_file',
# this load_dotenv() call is mainly for local development outside Docker.
# Docker will inject the environment variables from the .env file directly.
load_dotenv()


def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database using environment variables.

    Returns:
        psycopg2.connection: A connection object to the database.
                             Returns None if connection parameters are missing.

    Raises:
        psycopg2.OperationalError: If the database connection fails.
    """
    dbname = os.getenv("FLIPFORCE_POSTGRES_DB")
    user = os.getenv("FLIPFORCE_POSTGRES_USER")
    password = os.getenv("FLIPFORCE_POSTGRES_PASSWORD")
    host = os.getenv("FLIPFORCE_POSTGRES_HOST")  # Should be 'flipforce-db' in Docker
    port = os.getenv("FLIPFORCE_POSTGRES_PORT", "5432")  # Default to 5432 if not set

    if not all([dbname, user, password, host, port]):
        print("Database connection parameters are missing in environment variables.")
        # Or raise an error: raise ValueError("Database connection parameters missing")
        return None  # Or handle as appropriate for your application's startup

    return psycopg2.connect(
        dbname=dbname, user=user, password=password, host=host, port=port
    )


# Example of how you might want to pre-fetch and validate config at module load,
# though get_db_connection typically is called when a connection is needed.
# DB_CONFIG_VALID = all([
#     os.getenv("FLIPFORCE_POSTGRES_DB"),
#     os.getenv("FLIPFORCE_POSTGRES_USER"),
#     os.getenv("FLIPFORCE_POSTGRES_PASSWORD"),
#     os.getenv("FLIPFORCE_POSTGRES_HOST"),
#     os.getenv("FLIPFORCE_POSTGRES_PORT")
# ])

# if not DB_CONFIG_VALID:
#     print("WARNING: Not all FLIPFORCE database environment variables are set.")
