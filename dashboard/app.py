# dashboard/app.py

import dash
import dash_bootstrap_components as dbc
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import other modules after dotenv.load_dotenv()
from callbacks import register_callbacks  # noqa: E402
from config import DB_CONFIG, COLORS  # noqa: E402; For initial check and theme
from data_fetching import get_dashboard_db_engine  # noqa: E402; For startup test
from main_layout import create_layout  # noqa: E402

# Initialize the Dash app with a dark theme from Dash Bootstrap Components
# CYBORG is a good dark theme. LUX, DARKLY, SLATE are other options.
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],  # Apply the CYBORG dark theme
    suppress_callback_exceptions=True,
    meta_tags=[ # For responsiveness
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ]
)
server = app.server

app.title = "FlipForce Dashboard"
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
            "CRITICAL: Dashboard database configuration is incomplete. "
            "Set FLIPFORCE_POSTGRES_* env variables."
        )
        print(f"Loaded DB Config: {DB_CONFIG}")
    else:
        db_info = (
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
            f"{DB_CONFIG['dbname']} (User: {DB_CONFIG['user']})"
        )
        print(f"Dashboard starting with DB config: {db_info}")
        test_engine = None
        try:
            test_engine = get_dashboard_db_engine()
            if test_engine:
                print("Successfully created a test database engine.")
            else:
                print("Failed to create a test database engine. Check logs for errors.")
        except Exception as e:
            print(f"Error creating test database engine during startup: {e}")
        finally:
            if test_engine:
                test_engine.dispose()

        app.run(debug=True, host="0.0.0.0", port=8050)
