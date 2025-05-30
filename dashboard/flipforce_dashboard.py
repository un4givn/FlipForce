"""
Dash application for displaying FlipForce sold card events,
summarizing tier and series data, current pack values, and historical trends,
with continuous updates.
"""

import os

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import psycopg2
from dash import Input, Output, State, callback_context, dcc, html
from dotenv import load_dotenv

# Load environment variables from .env file (primarily for local development)
load_dotenv()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
server = app.server

# --- Configuration ---
DB_CONFIG = {
    "host": os.getenv("FLIPFORCE_POSTGRES_HOST", "flipforce-db"),
    "port": int(os.getenv("FLIPFORCE_POSTGRES_PORT", 5432)),
    "dbname": os.getenv("FLIPFORCE_POSTGRES_DB"),
    "user": os.getenv("FLIPFORCE_POSTGRES_USER"),
    "password": os.getenv("FLIPFORCE_POSTGRES_PASSWORD"),
}

PACK_CATEGORY_ORDER = ["Diamond", "Emerald", "Ruby", "Gold", "Silver", "Misc"]


# --- Data Fetching Functions ---
def get_dashboard_db_connection():
    """
    Establishes and returns a database connection for the dashboard.
    Handles potential missing configuration by printing an error.
    """
    if not all(
        [
            DB_CONFIG["dbname"],
            DB_CONFIG["user"],
            DB_CONFIG["password"],
            DB_CONFIG["host"],
        ]
    ):
        print(
            "[ERROR] Dashboard DB configuration is incomplete. "
            "Check environment variables."
        )
        return None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Dashboard failed to connect to database: {e}")
        return None


def fetch_main_dashboard_data(db_conn):
    """
    Fetches main data: sold card events (all attributes) and the LATEST
    total estimated value of available cards for each series.
    Uses the provided database connection.
    """
    if not db_conn:
        return pd.DataFrame()

    query_sold_cards = """
    SELECT
        sce.series_id, sce.card_id, sce.event_id, sce.tier AS card_tier,
        sce.player_name, sce.overall, sce.insert_name, sce.set_number,
        sce.set_name, sce.holo, sce.rarity, sce.parallel_number,
        sce.parallel_total, sce.parallel_name, sce.front_image, sce.back_image,
        sce.slab_kind, sce.grading_company,
        sce.estimated_value_cents AS sold_card_value_cents, sce.sold_at,
        psm.name AS pack_name, psm.tier AS pack_category
    FROM
        sold_card_events sce
    LEFT JOIN
        pack_series_metadata psm ON sce.series_id = psm.series_id
    ORDER BY sce.series_id, sce.sold_at DESC;
    """
    sold_cards_df = pd.read_sql(query_sold_cards, db_conn)
    if "sold_card_value_cents" in sold_cards_df.columns:
        sold_cards_df["sold_card_value_cents"] = pd.to_numeric(
            sold_cards_df["sold_card_value_cents"], errors="coerce"
        )
    if "overall" in sold_cards_df.columns:
        sold_cards_df["overall"] = pd.to_numeric(
            sold_cards_df["overall"], errors="coerce"
        )
    if "sold_at" in sold_cards_df.columns:
        sold_cards_df["sold_at"] = pd.to_datetime(sold_cards_df["sold_at"])

    query_latest_total_value = """
    WITH LatestPackValue AS (
        SELECT
            ptvs.series_id,
            ptvs.total_estimated_value_cents AS current_series_total_value_cents,
            ROW_NUMBER() OVER(
                PARTITION BY ptvs.series_id ORDER BY ptvs.snapshot_time DESC
            ) as rn
        FROM pack_total_value_snapshots ptvs
    )
    SELECT series_id, current_series_total_value_cents
    FROM LatestPackValue
    WHERE rn = 1;
    """
    latest_total_value_df = pd.read_sql(query_latest_total_value, db_conn)
    if "current_series_total_value_cents" in latest_total_value_df.columns:
        latest_total_value_df["current_series_total_value_cents"] = pd.to_numeric(
            latest_total_value_df["current_series_total_value_cents"], errors="coerce"
        )

    all_df = pd.DataFrame()
    if not sold_cards_df.empty:
        if not latest_total_value_df.empty:
            all_df = pd.merge(
                sold_cards_df, latest_total_value_df, on="series_id", how="left"
            )
        else:
            sold_cards_df["current_series_total_value_cents"] = np.nan
            all_df = sold_cards_df
    elif not latest_total_value_df.empty:
        query_pack_meta = (
            "SELECT series_id, name as pack_name, tier as pack_category "
            "FROM pack_series_metadata;"
        )
        pack_meta_df = pd.read_sql(query_pack_meta, db_conn)
        if not pack_meta_df.empty:
            all_df = pd.merge(
                latest_total_value_df, pack_meta_df, on="series_id", how="left"
            )
            cols_to_add_if_missing = [
                "card_id",
                "event_id",
                "card_tier",
                "player_name",
                "overall",
                "insert_name",
                "set_number",
                "set_name",
                "holo",
                "rarity",
                "parallel_number",
                "parallel_total",
                "parallel_name",
                "front_image",
                "back_image",
                "slab_kind",
                "grading_company",
                "sold_card_value_cents",
                "sold_at",
            ]
            for col in cols_to_add_if_missing:
                if col not in all_df.columns:
                    all_df[col] = np.nan
        else:
            all_df = latest_total_value_df
            cols_to_add_if_missing_alt = [
                "pack_name",
                "pack_category",
                "sold_card_value_cents",
                "card_tier",
                "event_id",
                "sold_at",
            ]
            for col in cols_to_add_if_missing_alt:
                if col not in all_df.columns:
                    all_df[col] = np.nan
    return all_df


def fetch_all_historical_pack_values(db_conn):
    """
    Fetches all historical pack value snapshots.
    Uses the provided database connection.
    """
    if not db_conn:
        return pd.DataFrame()

    query = """
    SELECT series_id, total_estimated_value_cents, snapshot_time
    FROM pack_total_value_snapshots
    ORDER BY series_id, snapshot_time ASC;
    """
    df = pd.read_sql(query, db_conn)
    if not df.empty:
        df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])
        if "total_estimated_value_cents" in df.columns:
            df["total_estimated_value_cents"] = pd.to_numeric(
                df["total_estimated_value_cents"], errors="coerce"
            )
    return df


# --- UI Component Generation ---
def make_series_cards(df_sorted_for_display, historical_pack_values_df):
    """
    Generates a list of Dash Bootstrap Components Cards for each series.
    """
    if df_sorted_for_display.empty:
        return html.Div(
            "No series data available to generate cards.", className="text-info"
        )

    cards = []
    if "series_id" not in df_sorted_for_display.columns:
        return html.Div("Data is missing 'series_id' column.", className="text-danger")

    unique_series_df = df_sorted_for_display.drop_duplicates(
        subset=["series_id"], keep="first"
    )

    for _, row in unique_series_df.iterrows():
        series_id = row["series_id"]
        pack_name_val = row.get("pack_name", "N/A")
        pack_category_val = row.get("pack_category", "N/A")

        group_df_for_series_sold_events = df_sorted_for_display[
            (df_sorted_for_display["series_id"] == series_id)
            & (df_sorted_for_display["event_id"].notna())
        ]
        display_pack_name = ""
        if pd.notna(pack_name_val) and pack_name_val:
            display_pack_name = pack_name_val
        display_pack_category = ""
        if pd.notna(pack_category_val) and pack_category_val:
            display_pack_category = pack_category_val

        if display_pack_category and display_pack_name:
            full_display_name = f"{display_pack_category} {display_pack_name}"
        elif display_pack_name:
            full_display_name = display_pack_name
        elif display_pack_category:
            full_display_name = display_pack_category
        else:
            full_display_name = str(series_id)

        total_sold = len(group_df_for_series_sold_events)
        card_tier_counts = {}
        if "card_tier" in group_df_for_series_sold_events:
            card_tier_counts = (
                group_df_for_series_sold_events["card_tier"].value_counts().to_dict()
            )

        avg_sold_value_cents_col = group_df_for_series_sold_events.get(
            "sold_card_value_cents"
        )
        avg_sold_value_cents = np.nan
        if total_sold > 0 and avg_sold_value_cents_col is not None:
            avg_sold_value_cents = np.nanmean(avg_sold_value_cents_col)
        avg_sold_value_display = (
            f"${avg_sold_value_cents / 100:.2f}"
            if pd.notna(avg_sold_value_cents)
            else "N/A"
        )

        current_total_pack_value_cents = row.get("current_series_total_value_cents")
        current_total_pack_value_display = (
            f"${current_total_pack_value_cents / 100:.2f}"
            if pd.notna(current_total_pack_value_cents)
            else "N/A"
        )

        button_header_text = (
            f"{full_display_name} — {total_sold} Sold — Pack Value: "
            f"{current_total_pack_value_display}"
        )

        card_body_items = []
        if total_sold > 0:
            card_body_items.extend(
                [
                    html.H6("Card Tier Breakdown (Sold)"),
                    html.Ul(
                        [
                            html.Li(f"{tier}: {count}")
                            for tier, count in card_tier_counts.items()
                        ]
                    ),
                    html.H6("Average Est. Value (Sold Cards)"),
                    html.P(avg_sold_value_display),
                ]
            )
        else:
            card_body_items.append(html.P("No sales data for this series yet."))

        card_body_items.extend(
            [
                html.H6("Current Total Pack Value (Est.)"),
                html.P(current_total_pack_value_display),
            ]
        )

        sold_cards_display_list = []
        if total_sold > 0:
            display_cols = [
                "card_id",
                "player_name",
                "card_tier",
                "overall",
                "insert_name",
                "set_name",
                "set_number",
                "holo",
                "rarity",
                "parallel_name",
                "parallel_number",
                "parallel_total",
                "grading_company",
                "slab_kind",
                "sold_card_value_cents",
                "sold_at",
                "front_image",
                "back_image",
                "event_id",
            ]
            for _, card_event_row in group_df_for_series_sold_events.iterrows():
                item_details_children = []
                card_identifier = card_event_row.get("player_name", "")
                if pd.isna(card_identifier) or str(card_identifier).strip() == "":
                    card_identifier = card_event_row.get(
                        "insert_name",
                        f"Card ID: {card_event_row.get('card_id', 'Unknown')}",
                    )
                else:
                    insert_name_val = card_event_row.get("insert_name")
                    if pd.notna(insert_name_val) and str(insert_name_val).strip() != "":
                        card_identifier += f" - {insert_name_val}"

                item_details_children.append(html.Strong(card_identifier))
                list_items_for_card = []
                for col in display_cols:
                    if col in card_event_row:
                        value = card_event_row[col]
                        col_display_name = col.replace("_", " ").title()
                        if pd.isna(value) or (
                            isinstance(value, str) and value.strip() == ""
                        ):
                            value_display = html.Em("N/A")
                        elif col == "sold_at":
                            value_display = (
                                pd.to_datetime(value).strftime("%Y-%m-%d %H:%M:%S UTC")
                                if pd.notna(value)
                                else html.Em("N/A")
                            )
                        elif col == "sold_card_value_cents":
                            value_display = (
                                f"${value / 100:.2f}"
                                if pd.notna(value)
                                else html.Em("N/A")
                            )
                            col_display_name = "Sold Value"
                        elif col == "overall" and pd.notna(value):
                            value_display = f"{int(value)}"
                        elif (
                            col in ["front_image", "back_image"]
                            and pd.notna(value)
                            and "http" in str(value).lower()
                        ):
                            value_display = html.A(
                                "View Image",
                                href=str(value),
                                target="_blank",
                                style={"fontSize": "0.9em"},
                            )
                        else:
                            value_display = str(value)
                        list_items_for_card.append(
                            html.Li(
                                f"{col_display_name}: {value_display}",
                                style={"lineHeight": "1.5"},
                            )
                        )
                item_details_children.append(
                    html.Ul(
                        list_items_for_card,
                        style={
                            "fontSize": "0.8rem",
                            "paddingLeft": "20px",
                            "listStyleType": "disc",
                            "marginBottom": "5px",
                        },
                    )
                )
                sold_cards_display_list.append(
                    dbc.ListGroupItem(
                        item_details_children,
                        style={"padding": "0.6rem 0.8rem", "backgroundColor": "#fff"},
                    )
                )
        sold_cards_scrolling_div_content = (
            dbc.ListGroup(sold_cards_display_list, flush=False, className="mb-2")
            if total_sold > 0
            else html.Em("No individual sold card details for this series.")
        )
        sold_cards_scrolling_div = html.Div(
            sold_cards_scrolling_div_content,
            style={
                "maxHeight": "400px",
                "overflowY": "auto",
                "border": "1px solid #dee2e6",
                "padding": "0px",
                "marginTop": "10px",
                "backgroundColor": "#f8f9fa",
            },
        )
        card_body_items.extend(
            [
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6(
                    "Recently Sold Card Details",
                    style={"marginTop": "0.5rem", "marginBottom": "0.5rem"},
                ),
                sold_cards_scrolling_div,
            ]
        )

        graph_figure_component = html.Em(
            "Not enough data to plot pack value trend for this series."
        )
        if (
            historical_pack_values_df is not None
            and not historical_pack_values_df.empty
            and "series_id" in historical_pack_values_df.columns
        ):
            series_historical_values = historical_pack_values_df[
                historical_pack_values_df["series_id"] == series_id
            ].copy()

            if (
                not series_historical_values.empty
                and len(series_historical_values) > 1
                and "snapshot_time" in series_historical_values.columns
                and "total_estimated_value_cents" in series_historical_values.columns
            ):
                series_historical_values.sort_values(by="snapshot_time", inplace=True)
                series_historical_values["total_pack_value_dollars"] = (
                    series_historical_values["total_estimated_value_cents"] / 100.0
                )

                fig = px.line(
                    series_historical_values,
                    x="snapshot_time",
                    y="total_pack_value_dollars",
                    labels={
                        "snapshot_time": "Date",
                        "total_pack_value_dollars": "Total Pack Value ($)",
                    },
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=250,
                    yaxis_title="Value ($)",
                    xaxis_title=None,
                    showlegend=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10),
                )
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#e0e0e0")
                fig.update_yaxes(
                    showgrid=True, gridwidth=1, gridcolor="#e0e0e0", tickprefix="$"
                )
                graph_figure_component = dcc.Graph(
                    figure=fig, config={"displayModeBar": False}
                )
            elif not series_historical_values.empty:
                graph_figure_component = html.Em(
                    "Only one data point available; cannot plot trend line."
                )

        card_body_items.extend(
            [
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6(
                    "Historical Pack Value Trend",
                    style={"marginTop": "0.5rem", "marginBottom": "0.5rem"},
                ),
                graph_figure_component,
            ]
        )

        card_body_content = html.Div(card_body_items)

        cards.append(
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Button(
                            button_header_text,
                            id={"type": "series-toggle", "index": str(series_id)},
                            className="w-100 text-start",
                            color="secondary",
                        )
                    ),
                    dbc.Collapse(
                        dbc.CardBody(card_body_content),
                        id={"type": "series-collapse", "index": str(series_id)},
                        is_open=False,
                    ),
                ],
                className="mb-3 shadow-sm",
            )
        )
    return cards


# --- Application Layout ---
app.layout = dbc.Container(
    [
        dcc.Interval(
            id="initial-load-interval",
            interval=5 * 60 * 1000,
            n_intervals=0,
            max_intervals=-1,
        ),
        html.H2("📦 FlipForce Sold Tier + Series Summary", className="my-4"),
        dbc.Card(
            [
                dbc.CardHeader(
                    dbc.Button(
                        "Click to Expand Overall Card Tier Summary (All Sold Cards)",
                        id="tier-toggle",
                        color="primary",
                        className="w-100 text-start",
                    )
                ),
                dbc.Collapse(
                    dbc.CardBody(id="tier-body"), id="tier-collapse", is_open=False
                ),
            ],
            className="mb-4",
        ),
        html.Div(id="series-card-container"),
    ],
    fluid=True,
)


# --- Callbacks ---
@app.callback(
    Output("tier-body", "children"),
    Output("series-card-container", "children"),
    Input("initial-load-interval", "n_intervals"),
)
def load_all_data(n_intervals):
    """
    Main callback to load and refresh all dashboard data.
    Connects to the database, fetches data, processes it, and
    generates UI components.
    (Docstring: Detail error handling, sorting, conditional content.)
    """  # Line 571 fix
    df = pd.DataFrame()
    historical_df = pd.DataFrame()
    conn = None
    tier_summary_content = html.P("No card tier data to display.")
    series_cards_content = html.Div(
        "Loading data or no data available...", className="text-info"
    )

    try:
        conn = get_dashboard_db_connection()
        if conn:
            df = fetch_main_dashboard_data(conn)
            historical_df = fetch_all_historical_pack_values(conn)
        else:
            series_cards_content = html.Div(
                "Failed to connect to the database. "
                "Please check configuration and logs.",
                className="text-danger",
            )
            return tier_summary_content, series_cards_content

    except Exception as e:
        print(f"[ERROR] Data fetch or processing failed in load_all_data: {e}")
        import traceback

        traceback.print_exc()
        series_cards_content = html.Div(
            f"Error loading or processing data: {str(e)}", className="text-danger"
        )
    finally:
        if conn:
            conn.close()

    if not df.empty:
        if "pack_category" in df.columns:
            df["pack_category_ordered"] = pd.Categorical(
                df["pack_category"].fillna("Misc"),
                categories=PACK_CATEGORY_ORDER,
                ordered=True,
            )
            df.sort_values(
                by=["pack_category_ordered", "pack_name", "series_id", "sold_at"],
                ascending=[True, True, True, False],
                inplace=True,
                na_position="last",
            )
        else:
            sort_by_cols = []
            if "series_id" in df.columns:
                sort_by_cols.append("series_id")
            if "sold_at" in df.columns:
                sort_by_cols.append("sold_at")
            if sort_by_cols:
                df.sort_values(
                    by=sort_by_cols,
                    ascending=[True, False] if len(sort_by_cols) == 2 else True,
                    inplace=True,
                )
            print(
                "[WARN] 'pack_category' column not found for primary sorting. "
                "Attempted fallback sort."
            )

        sold_cards_subset = pd.DataFrame()
        if "event_id" in df.columns:
            sold_cards_subset = df[df["event_id"].notna()]

        if (
            "card_tier" in sold_cards_subset.columns
            and not sold_cards_subset["card_tier"].dropna().empty
        ):
            tier_df_summary = (
                sold_cards_subset["card_tier"].value_counts().reset_index()
            )
            tier_df_summary.columns = ["card_tier_name", "count"]
            tier_list_items = [
                html.Li(f"{row['card_tier_name']}: {row['count']}")
                for _, row in tier_df_summary.iterrows()
            ]
            tier_summary_content = html.Ul(tier_list_items)
        else:
            tier_summary_content = html.P("No sold card tier data to summarize.")

        series_cards_content = make_series_cards(df, historical_df)
    elif df.empty and not historical_df.empty:
        series_cards_content = make_series_cards(df, historical_df)
        if isinstance(
            series_cards_content, html.Div
        ) and "No series data available" in str(series_cards_content.children):
            series_cards_content = html.Div(
                "No current sales data available, but historical pack value "
                "trends might be shown.",
                className="text-info",
            )
    elif (
        df.empty
        and historical_df.empty
        and (
            isinstance(series_cards_content, html.Div)
            and series_cards_content.children == "Loading data or no data available..."
        )
    ):
        # If still default message and both DFs are empty, implies no data fetched
        # (or DB connection failed earlier).
        tier_summary_content = html.Div(
            "No data available from the database for tier summary."
        )
        series_cards_content = html.Div(
            "No data available from the database for series cards.",
            className="text-danger",
        )
    # If series_cards_content was set to an error message, it persists.

    return tier_summary_content, series_cards_content


@app.callback(
    Output("tier-collapse", "is_open"),
    Input("tier-toggle", "n_clicks"),
    State("tier-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_tier_summary_collapse(n_clicks, is_open):
    """Toggles the collapse state of the overall tier summary."""
    if n_clicks:
        return not is_open
    return is_open


@app.callback(
    Output({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    Input({"type": "series-toggle", "index": dash.ALL}, "n_clicks"),
    State({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    State({"type": "series-toggle", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def toggle_individual_series_collapse(n_clicks_list, current_is_open_list, button_ids):
    """Toggles the collapse state of an individual series card."""
    ctx = callback_context
    if not ctx.triggered_id or not n_clicks_list:
        return current_is_open_list

    triggered_button_id_str = ctx.triggered_id["index"]

    new_is_open_list = list(current_is_open_list)
    for i, button_id_dict in enumerate(button_ids):
        if str(button_id_dict["index"]) == triggered_button_id_str:
            # Check if the specific button that was clicked has a non-None n_clicks
            if n_clicks_list[i] is not None:
                new_is_open_list[i] = not current_is_open_list[i]
            break

    return new_is_open_list


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
            "Please set the FLIPFORCE_POSTGRES_* environment variables."
        )
        print(f"Loaded DB Config: {DB_CONFIG}")
    else:
        print(
            f"Dashboard starting with DB config: {DB_CONFIG['host']}:"
            f"{DB_CONFIG['port']}/{DB_CONFIG['dbname']} "
            f"(User: {DB_CONFIG['user']})"
        )
        app.run(debug=True, host="0.0.0.0", port=8050)
