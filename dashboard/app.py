# dashboard/app.py

import dash
import dash_bootstrap_components as dbc
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from callbacks import register_callbacks
from config import DB_CONFIG  # For initial check
from data_fetching import get_dashboard_db_engine  # For the startup test
from main_layout import create_layout

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,  # Necessary if callbacks are in other files or layout is dynamic
)
server = app.server

app.title = "FlipForce Dashboard"  # Optional: Set a browser tab title
app.layout = create_layout()
register_callbacks(app)

if __name__ == "__main__":
    if not all(
        [
            DB_CONFIG["dbname"],
            DB_CONFIG["user"],
            DB_CONFIG["password"],
            DB_CONFIG["host"],
        ]
    ):
        print(
            "CRITICAL: Dashboard database configuration is incomplete. Set FLIPFORCE_POSTGRES_* env variables."
        )
        print(f"Loaded DB Config: {DB_CONFIG}")
    else:
        print(
            f"Dashboard starting with DB config: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']} (User: {DB_CONFIG['user']})"
        )
        # Optional: Test DB connection on startup
        test_engine = None
        try:
            test_engine = get_dashboard_db_engine()
            if test_engine:
                print("Successfully created a test database engine.")
            else:
                print("Failed to create a test database engine. Check logs for errors.")
                # Consider exiting if this is critical:
                # import sys
                # sys.exit(1)
        except Exception as e:
            print(f"Error creating test database engine during startup: {e}")
        finally:
            if test_engine:
                test_engine.dispose()

        app.run(debug=True, host="0.0.0.0", port=8050)
