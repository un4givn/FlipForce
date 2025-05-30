# dashboard/main_layout.py
import dash_bootstrap_components as dbc
from dash import dcc, html


def create_layout():
    """Creates the main layout for the Dash application."""
    return dbc.Container(
        [
            dcc.Interval(
                id="data-refresh-interval", interval=5 * 60 * 1000, n_intervals=0
            ),  # 5 minutes
            html.H2(
                "📦 FlipForce Dashboard - ROI Enhanced", className="my-4 text-center"
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Button(
                            "Overall Sold Card Tier Summary",
                            id="tier-toggle",
                            color="primary",
                            className="w-100 text-start",
                        )
                    ),
                    dbc.Collapse(
                        dbc.CardBody(id="tier-body-content"),
                        id="tier-collapse",
                        is_open=False,
                    ),
                ],
                className="mb-4",
            ),
            html.Div(
                id="series-card-container", children=[html.P("Loading series data...")]
            ),
        ],
        fluid=True,
    )
