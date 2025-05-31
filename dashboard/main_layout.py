# dashboard/main_layout.py
import dash_bootstrap_components as dbc
from dash import dcc, html
from config import COLORS # Import color configuration

def create_layout():
    """Creates the main layout for the Dash application with a new look and feel."""
    return dbc.Container(
        [
            dcc.Interval(
                id="data-refresh-interval",
                interval=5 * 60 * 1000,  # 5 minutes in milliseconds
                n_intervals=0
            ),
            # Header section
            dbc.Row(
                dbc.Col(
                    html.H1(
                        "FlipForce Dashboard",
                        className="my-4 text-center fw-bold",
                        style={"color": COLORS["primary"]} # Use primary color for title
                    ),
                    width=12
                ),
                className="mb-4"
            ),

            # Overall Sold Card Tier Summary Card
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H4("Overall Sold Card Tier Summary", className="mb-0"),
                        style={"backgroundColor": COLORS["card_background"], "borderColor": COLORS["border_color"]}
                    ),
                    dbc.Collapse(
                        dbc.CardBody(id="tier-body-content", style={"color": COLORS["text"]}),
                        id="tier-collapse",
                        is_open=True, # Keep it open by default, or set to False
                    ),
                    dbc.CardFooter(
                        dbc.Button(
                            "Toggle Summary Details",
                            id="tier-toggle",
                            color="secondary", # Use a less prominent color for toggle
                            className="w-100",
                            outline=True
                        ),
                        style={"backgroundColor": COLORS["card_background"], "borderColor": COLORS["border_color"], "borderTop": f"1px solid {COLORS['border_color']}"}
                    )
                ],
                className="mb-4 shadow", # Add shadow for depth
                style={"backgroundColor": COLORS["card_background"], "borderColor": COLORS["border_color"]}
            ),

            # Container for Series Cards
            html.Div(
                id="series-card-container",
                children=[
                    dbc.Spinner(color=COLORS["primary"], children=[html.P("Loading series data...", className="text-center", style={"color": COLORS["text"]})])
                ]
            ),
        ],
        fluid=True,
        className="py-3", # Add some padding to the overall container
        style={"backgroundColor": COLORS["background"], "minHeight": "100vh"} # Ensure background covers full height
    )
