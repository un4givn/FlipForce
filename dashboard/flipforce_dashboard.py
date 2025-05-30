"""
Dash application for displaying FlipForce sold card events,
summarizing tier and series data, current pack values, historical trends,
and ROI analysis with continuous updates.
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

PACK_CATEGORY_ORDER = ["Diamond", "Emerald", "Ruby", "Gold", "Silver", "Misc.", "Misc", "Unknown Category"]
STATIC_PACK_COSTS_CENTS = {
    "Diamond": 100000, "Emerald": 50000, "Ruby": 25000,
    "Gold": 10000, "Silver": 5000,
    "Misc.": 2500, "Misc": 2500
}

# --- Data Fetching Functions ---
def get_dashboard_db_connection():
    """Establishes and returns a database connection for the dashboard."""
    if not all([DB_CONFIG["dbname"], DB_CONFIG["user"], DB_CONFIG["password"], DB_CONFIG["host"]]):
        print("[ERROR] Dashboard DB configuration is incomplete. Check environment variables.")
        return None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Dashboard failed to connect to database: {e}")
        return None

def fetch_sold_cards_and_pack_metadata(db_conn):
    """Fetches sold card events joined with pack series metadata."""
    if not db_conn: return pd.DataFrame()
    query = """
    SELECT
        sce.series_id, sce.card_id, sce.event_id, sce.tier AS card_tier,
        sce.player_name, sce.overall, sce.insert_name, sce.set_number,
        sce.set_name, sce.holo, sce.rarity, sce.parallel_number,
        sce.parallel_total, sce.parallel_name, sce.front_image, sce.back_image,
        sce.slab_kind, sce.grading_company,
        sce.estimated_value_cents AS sold_card_value_cents, sce.sold_at,
        psm.name AS pack_name, psm.tier AS pack_category
    FROM sold_card_events sce
    LEFT JOIN pack_series_metadata psm ON sce.series_id = psm.series_id
    ORDER BY sce.series_id, sce.sold_at DESC;
    """
    df = pd.read_sql(query, db_conn)
    if not df.empty:
        for col in ["sold_card_value_cents", "overall"]: # Ensure numeric types [cite: 1]
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors="coerce")
        if "sold_at" in df.columns: df["sold_at"] = pd.to_datetime(df["sold_at"])
    return df

def fetch_pack_total_value_data(db_conn):
    """Fetches current total available value (sum of cards) and its historical min/max."""
    if not db_conn: return pd.DataFrame(), pd.DataFrame()

    query_latest_total_value = """
    WITH LatestPackValue AS (
        SELECT series_id, total_estimated_value_cents AS current_total_available_value_cents,
               ROW_NUMBER() OVER(PARTITION BY series_id ORDER BY snapshot_time DESC) as rn
        FROM pack_total_value_snapshots
    ) SELECT series_id, current_total_available_value_cents FROM LatestPackValue WHERE rn = 1;
    """
    latest_df = pd.read_sql(query_latest_total_value, db_conn)
    if not latest_df.empty and "current_total_available_value_cents" in latest_df.columns:
        latest_df["current_total_available_value_cents"] = pd.to_numeric(latest_df["current_total_available_value_cents"], errors="coerce")

    query_min_max_total_value = """
    SELECT series_id,
           MIN(total_estimated_value_cents) as min_historical_total_value_cents,
           MAX(total_estimated_value_cents) as max_historical_total_value_cents
    FROM pack_total_value_snapshots GROUP BY series_id;
    """
    min_max_df = pd.read_sql(query_min_max_total_value, db_conn)
    return latest_df, min_max_df

def fetch_historical_value_trend_data(db_conn):
    """Fetches all historical total available values (sum of cards) for trend graphs."""
    if not db_conn: return pd.DataFrame()
    query = """
    SELECT series_id, total_estimated_value_cents, snapshot_time
    FROM pack_total_value_snapshots
    ORDER BY series_id, snapshot_time ASC;
    """
    df = pd.read_sql(query, db_conn)
    if not df.empty:
        df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])
        if "total_estimated_value_cents" in df.columns:
            df["total_estimated_value_cents"] = pd.to_numeric(df["total_estimated_value_cents"], errors="coerce")
    return df

def fetch_ev_roi_data(db_conn):
    """Fetches latest EV/ROI and historical min/max ROI for the dashboard."""
    if not db_conn: return pd.DataFrame(), pd.DataFrame()

    query_latest_ev_roi = """
    WITH LatestEVROI AS (
        SELECT series_id, expected_value_cents, static_pack_cost_cents, roi,
               ROW_NUMBER() OVER(PARTITION BY series_id ORDER BY snapshot_time DESC) as rn
        FROM pack_ev_roi_snapshots
    ) SELECT series_id, expected_value_cents, static_pack_cost_cents, roi FROM LatestEVROI WHERE rn = 1;
    """
    latest_ev_roi_df = pd.read_sql(query_latest_ev_roi, db_conn)

    query_min_max_roi = """
    SELECT series_id,
           MIN(roi) as min_historical_roi,
           MAX(roi) as max_historical_roi
    FROM pack_ev_roi_snapshots GROUP BY series_id;
    """
    min_max_roi_df = pd.read_sql(query_min_max_roi, db_conn)
    return latest_ev_roi_df, min_max_roi_df


# --- UI Component Generation ---
def make_series_cards(base_series_df, hist_val_trend_data_for_graph,
                      all_sold_cards_df):
    """
    Generates a list of Dash Bootstrap Components (dbc) Cards for each series.
    base_series_df is expected to be pre-merged with latest total values, EV/ROI, and historical min/max for these.
    all_sold_cards_df is the raw result from fetch_sold_cards_and_pack_metadata.
    """
    if base_series_df.empty:
        return html.Div("No series data available to generate cards.", className="text-info")
    if "series_id" not in base_series_df.columns:
        return html.Div("Essential 'series_id' column missing from display data.", className="text-danger")

    cards = []
    # base_series_df should already have one unique row per series after merges in load_all_dashboard_data
    unique_series_display_df = base_series_df

    for _, row in unique_series_display_df.iterrows():
        series_id = row["series_id"]
        pack_name_val = row.get("pack_name", "N/A")
        pack_category_val = row.get("pack_category", "Unknown Category")

        # Filter all_sold_cards_df for this specific series to get its sold events
        series_specific_sold_events = all_sold_cards_df[
            (all_sold_cards_df["series_id"] == series_id) & (all_sold_cards_df["event_id"].notna())
        ] if not all_sold_cards_df.empty else pd.DataFrame()

        total_sold_for_this_series = len(series_specific_sold_events)

        # Tier breakdown percentages for sold cards of this series
        tier_summary_list_items = []
        if total_sold_for_this_series > 0 and "card_tier" in series_specific_sold_events.columns:
            card_tier_counts = series_specific_sold_events["card_tier"].value_counts()
            for tier, count in card_tier_counts.items():
                percentage = (count / total_sold_for_this_series) * 100
                tier_display_name = tier if pd.notna(tier) else "Unspecified Tier"
                tier_summary_list_items.append(html.Li(f"{tier_display_name}: {count} ({percentage:.1f}%)"))
        else:
            tier_summary_list_items.append(html.Li("No sales data for tier breakdown for this series."))

        avg_sold_val_cents = series_specific_sold_events["sold_card_value_cents"].mean() if total_sold_for_this_series > 0 else np.nan
        avg_sold_val_display = f"${avg_sold_val_cents / 100:.2f}" if pd.notna(avg_sold_val_cents) else "N/A"

        # Current Total Available Value (sum of all cards in pack) - from pre-merged base_series_df
        curr_total_avail_val_cents = row.get("current_total_available_value_cents")
        curr_total_avail_val_display = f"${curr_total_avail_val_cents / 100:.2f}" if pd.notna(curr_total_avail_val_cents) else "N/A"

        # Historical Min/Max Total Available Value - from pre-merged base_series_df
        min_hist_total_val_display = f"${row.get('min_historical_total_value_cents', np.nan) / 100:.2f}" if pd.notna(row.get('min_historical_total_value_cents')) else "N/A"
        max_hist_total_val_display = f"${row.get('max_historical_total_value_cents', np.nan) / 100:.2f}" if pd.notna(row.get('max_historical_total_value_cents')) else "N/A"

        # Static Pack Cost
        static_cost_val = STATIC_PACK_COSTS_CENTS.get(pack_category_val)
        static_cost_display = f"${static_cost_val / 100:.2f}" if static_cost_val is not None else "N/A"

        # EV & ROI - from pre-merged base_series_df
        current_ev_cents = row.get("expected_value_cents")
        current_roi_val = row.get("roi")
        current_ev_display = f"${current_ev_cents / 100:.2f}" if pd.notna(current_ev_cents) else "N/A"
        current_roi_display = f"{current_roi_val:.2%}" if pd.notna(current_roi_val) and current_roi_val is not None and not (isinstance(current_roi_val, float) and np.isinf(current_roi_val)) else "N/A"

        min_hist_roi_val = row.get('min_historical_roi', np.nan)
        max_hist_roi_val = row.get('max_historical_roi', np.nan)
        min_hist_roi_display = f"{min_hist_roi_val:.2%}" if pd.notna(min_hist_roi_val) and not (isinstance(min_hist_roi_val, float) and np.isinf(min_hist_roi_val)) else "N/A"
        max_hist_roi_display = f"{max_hist_roi_val:.2%}" if pd.notna(max_hist_roi_val) and not (isinstance(max_hist_roi_val, float) and np.isinf(max_hist_roi_val)) else "N/A"

        full_display_name_card = f"{pack_category_val} {pack_name_val}" if pack_category_val not in ["Unknown Category", None] else pack_name_val
        button_header_text = f"{full_display_name_card} — ROI: {current_roi_display} — EV: {current_ev_display}"

        card_body_items = [
            html.H6("Sales Summary", className="mt-2"),
            dbc.Row([
                dbc.Col(html.P(f"Total Sold Cards: {total_sold_for_this_series}"), width=6),
                dbc.Col(html.P(f"Avg. Sold Card Value: {avg_sold_val_display}"), width=6),
            ]),
            html.H6("Card Tier Breakdown (Sold Hits)"),
            html.Ul(tier_summary_list_items),
            html.Hr(),
            html.H6("Pack Valuation Metrics"),
            dbc.Row([
                dbc.Col(html.P(f"Static Pack Cost: {static_cost_display}"), width=6),
                dbc.Col(html.P(f"Current EV (per pack): {current_ev_display}"), width=6),
            ]),
            dbc.Row([
                dbc.Col(html.P(f"Current ROI (vs Static Cost): {current_roi_display}"), width=6),
            ]),
            dbc.Row([
                dbc.Col(html.P(f"Historical Min ROI: {min_hist_roi_display}"), width=6),
                dbc.Col(html.P(f"Historical Max ROI: {max_hist_roi_display}"), width=6),
            ]),
            html.Hr(),
            html.H6("Pack Contents Value (Sum of all current cards)"),
            dbc.Row([
                dbc.Col(html.P(f"Current Total Available Value: {curr_total_avail_val_display}"),width=12),
            ]),
            dbc.Row([
                dbc.Col(html.P(f"Historical Min Available Value: {min_hist_total_val_display}"),width=6),
                dbc.Col(html.P(f"Historical Max Available Value: {max_hist_total_val_display}"),width=6),
            ]),
        ]

        # Sold cards list (only if there are sales for this series)
        if total_sold_for_this_series > 0:
            sold_cards_display_list_ui = [] # Renamed to avoid conflict
            # Define which columns to show for each sold card and their display order
            display_cols_for_sold_cards = [
                "player_name", "card_tier", "overall", "insert_name", # Added insert_name
                "sold_card_value_cents", "sold_at", "front_image"
            ]
            for _, card_event_row in series_specific_sold_events.head(10).iterrows(): # Display top 10 recent
                item_details_children = []
                # Create a user-friendly identifier for the card
                card_identifier = card_event_row.get("player_name", "")
                if pd.isna(card_identifier) or str(card_identifier).strip() == "":
                    card_identifier = card_event_row.get("insert_name", f"Card ID: {card_event_row.get('card_id', 'Unknown')}")
                else:
                    insert_name_val = card_event_row.get("insert_name")
                    if pd.notna(insert_name_val) and str(insert_name_val).strip() != "":
                        card_identifier += f" - {insert_name_val}"

                item_details_children.append(html.Strong(card_identifier))
                list_items_for_card_display = []
                for col_sold in display_cols_for_sold_cards:
                    if col_sold in card_event_row:
                        value = card_event_row[col_sold]
                        col_display_name_sold = col_sold.replace("_", " ").title()
                        if pd.isna(value) or (isinstance(value, str) and value.strip() == ""): value_display = html.Em("N/A")
                        elif col_sold == "sold_at": value_display = pd.to_datetime(value).strftime("%Y-%m-%d %H:%M") if pd.notna(value) else html.Em("N/A")
                        elif col_sold == "sold_card_value_cents": value_display = f"${value / 100:.2f}" if pd.notna(value) else html.Em("N/A")
                        elif col_sold == "overall" and pd.notna(value): value_display = f"{int(value)}"
                        elif col_sold == "front_image" and pd.notna(value) and "http" in str(value).lower():
                            value_display = html.A("Image", href=str(value), target="_blank", style={"fontSize": "0.8em"})
                        else: value_display = str(value)
                        list_items_for_card_display.append(html.Li([html.Span(f"{col_display_name_sold}: ", style={'fontWeight': '500'}), value_display], style={"lineHeight": "1.4", "fontSize":"0.85rem"}))
                item_details_children.append(html.Ul(list_items_for_card_display, style={"fontSize": "0.8rem", "paddingLeft": "15px", "listStyleType": "disc", "marginBottom": "3px"}))
                sold_cards_display_list_ui.append(dbc.ListGroupItem(item_details_children, style={"padding": "0.5rem 0.7rem"}))

            sold_cards_scrolling_div_content = dbc.ListGroup(sold_cards_display_list_ui, flush=True)
            card_body_items.extend([
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6("Recently Sold Card Details (Max 10 shown)", style={"marginTop": "0.5rem", "marginBottom": "0.5rem"}),
                html.Div(sold_cards_scrolling_div_content, style={"maxHeight": "300px", "overflowY": "auto", "border": "1px solid #eee", "padding": "0px", "marginTop": "10px"})
            ])
        else:
             card_body_items.extend([html.Hr(), html.P(html.Em("No sales recorded for this series yet."))])

        # Historical total available pack value trend graph
        graph_figure_component = html.Em("Not enough data to plot pack value trend.")
        if hist_val_trend_data_for_graph is not None and not hist_val_trend_data_for_graph.empty:
            # Filter graph data for the current series_id
            series_hist_val_for_graph = hist_val_trend_data_for_graph[hist_val_trend_data_for_graph["series_id"] == series_id].copy()
            if not series_hist_val_for_graph.empty and len(series_hist_val_for_graph) > 1:
                series_hist_val_for_graph["total_pack_value_dollars"] = series_hist_val_for_graph["total_estimated_value_cents"] / 100.0
                fig = px.line(series_hist_val_for_graph, x="snapshot_time", y="total_pack_value_dollars", labels={"snapshot_time": "Date", "total_pack_value_dollars": "Total Value ($)"})
                fig.update_layout(margin=dict(l=10,r=10,t=30,b=10), height=200, yaxis_title="Value ($)", xaxis_title=None, showlegend=False, font=dict(size=10))
                graph_figure_component = dcc.Graph(figure=fig, config={"displayModeBar": False})
            elif not series_hist_val_for_graph.empty: # Only one data point
                graph_figure_component = html.Em("Only one data point for total pack value trend.")

        card_body_items.extend([
             html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
             html.H6("Historical Total Available Pack Value Trend", style={"marginTop": "0.5rem", "marginBottom": "0.5rem"}),
             graph_figure_component
        ])

        cards.append(
            dbc.Card([
                dbc.CardHeader(dbc.Button(button_header_text, id={"type": "series-toggle", "index": str(series_id)}, className="w-100 text-start", color="info")),
                dbc.Collapse(dbc.CardBody(html.Div(card_body_items)), id={"type": "series-collapse", "index": str(series_id)}, is_open=False),
            ], className="mb-3 shadow-sm")
        )
    return cards if cards else html.Div("No series information processed for display.", className="text-warning")


# --- Application Layout ---
app.layout = dbc.Container([
    dcc.Interval(id="data-refresh-interval", interval= 5 * 60 * 1000, n_intervals=0), # 5 minutes
    html.H2("📦 FlipForce Dashboard - ROI Enhanced", className="my-4 text-center"),
    dbc.Card([
        dbc.CardHeader(dbc.Button("Overall Sold Card Tier Summary", id="tier-toggle", color="primary", className="w-100 text-start")),
        dbc.Collapse(dbc.CardBody(id="tier-body-content"), id="tier-collapse", is_open=False),
    ], className="mb-4"),
    html.Div(id="series-card-container", children=[html.P("Loading series data...")]),
], fluid=True)

# --- Callbacks ---
@app.callback(
    Output("tier-body-content", "children"),
    Output("series-card-container", "children"),
    Input("data-refresh-interval", "n_intervals"),
)
def load_all_dashboard_data(n_intervals):
    conn = None
    try:
        conn = get_dashboard_db_connection()
        if not conn:
            error_message = "Failed to connect to the database. Please check configuration and logs."
            return html.P(error_message, className="text-danger"), html.Div(error_message, className="text-danger")

        df_sold_cards_and_meta = fetch_sold_cards_and_pack_metadata(conn) # Has all sold cards and pack_category
        df_latest_total_val, df_hist_min_max_total_val = fetch_pack_total_value_data(conn)
        df_hist_val_trend_graph_data = fetch_historical_value_trend_data(conn) # For the line graph
        df_latest_ev_roi, df_hist_min_max_roi = fetch_ev_roi_data(conn)

        # --- Prepare overall tier summary (from all sold cards) ---
        overall_tier_summary_content = html.P("No card tier data to display for overall summary.")
        if not df_sold_cards_and_meta.empty and "event_id" in df_sold_cards_and_meta.columns:
            # Use df_sold_cards_and_meta directly as it contains all sold events
            all_sold_cards_for_summary = df_sold_cards_and_meta[df_sold_cards_and_meta["event_id"].notna()]
            if not all_sold_cards_for_summary.empty and "card_tier" in all_sold_cards_for_summary.columns and \
               not all_sold_cards_for_summary["card_tier"].dropna().empty:
                overall_tier_counts = all_sold_cards_for_summary["card_tier"].value_counts()
                total_overall_sold_count = overall_tier_counts.sum() # Sum of counts of each tier
                overall_tier_list_items = []
                if total_overall_sold_count > 0:
                    for tier, count in overall_tier_counts.items():
                        percentage = (count / total_overall_sold_count) * 100
                        tier_display = tier if pd.notna(tier) else "Unspecified"
                        overall_tier_list_items.append(html.Li(f"{tier_display}: {count} ({percentage:.1f}%)"))
                overall_tier_summary_content = html.Ul(overall_tier_list_items if overall_tier_list_items else [html.Li("No tier data in sold cards.")])
            else: # No 'card_tier' column or all NaNs
                overall_tier_summary_content = html.P("No card tier data in sold cards for summary.")
        else: # df_sold_cards_and_meta is empty or no 'event_id'
            overall_tier_summary_content = html.P("No sold card events found for overall summary.")


        # --- Consolidate data for series cards ---
        # Start with unique series from metadata. This ensures all packs defined in metadata are listed.
        df_all_series_meta_from_db = pd.read_sql("SELECT series_id, name as pack_name, tier as pack_category FROM pack_series_metadata", conn)
        
        if df_all_series_meta_from_db.empty:
             return overall_tier_summary_content, html.Div("No pack series found in metadata. Tracker might need to run.", className="text-warning")

        # Merge other dataframes onto this base list of series
        df_display_for_cards = df_all_series_meta_from_db.copy()

        if not df_latest_total_val.empty:
            df_display_for_cards = pd.merge(df_display_for_cards, df_latest_total_val, on="series_id", how="left")
        else: # Ensure column exists if merge partner is empty
            df_display_for_cards["current_total_available_value_cents"] = np.nan
        
        if not df_hist_min_max_total_val.empty:
            df_display_for_cards = pd.merge(df_display_for_cards, df_hist_min_max_total_val, on="series_id", how="left")
        else:
            df_display_for_cards["min_historical_total_value_cents"] = np.nan
            df_display_for_cards["max_historical_total_value_cents"] = np.nan

        if not df_latest_ev_roi.empty:
            df_display_for_cards = pd.merge(df_display_for_cards, df_latest_ev_roi, on="series_id", how="left")
        else:
            df_display_for_cards["expected_value_cents"] = np.nan
            df_display_for_cards["static_pack_cost_cents"] = np.nan # Though this is also in STATIC_PACK_COSTS_CENTS
            df_display_for_cards["roi"] = np.nan
            
        if not df_hist_min_max_roi.empty:
            df_display_for_cards = pd.merge(df_display_for_cards, df_hist_min_max_roi, on="series_id", how="left")
        else:
            df_display_for_cards["min_historical_roi"] = np.nan
            df_display_for_cards["max_historical_roi"] = np.nan
        
        # Sort the consolidated DataFrame for display order
        if "pack_category" in df_display_for_cards.columns:
            df_display_for_cards["pack_category_ordered"] = pd.Categorical(
                df_display_for_cards["pack_category"].fillna("Unknown Category"), categories=PACK_CATEGORY_ORDER, ordered=True
            )
            df_display_for_cards.sort_values(
                by=["pack_category_ordered", "pack_name", "series_id"],
                ascending=[True, True, True], inplace=True, na_position="last"
            )
        
        # df_sold_cards_and_meta has all sold events needed by make_series_cards for filtering per series
        series_cards_ui = make_series_cards(
            df_display_for_cards, # This is the primary df with one row per series and all merged latest data
            df_hist_val_trend_graph_data,  # For the trend graph
            df_sold_cards_and_meta     # Contains all sold card events for per-series processing
        )
        
        return overall_tier_summary_content, series_cards_ui

    except Exception as e:
        print(f"[ERROR] Callback load_all_dashboard_data failed: {e}")
        import traceback; traceback.print_exc()
        error_msg = f"Error loading dashboard: {str(e)}"
        return html.P(error_msg, className="text-danger"), html.Div(error_msg, className="text-danger")
    finally:
        if conn: conn.close()

@app.callback(Output("tier-collapse", "is_open"), Input("tier-toggle", "n_clicks"), State("tier-collapse", "is_open"), prevent_initial_call=True)
def toggle_tier_summary_collapse(n_clicks, is_open):
    return not is_open if n_clicks else is_open

@app.callback(
    Output({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    Input({"type": "series-toggle", "index": dash.ALL}, "n_clicks"),
    State({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    State({"type": "series-toggle", "index": dash.ALL}, "id"),
    prevent_initial_call=True)
def toggle_individual_series_collapse(n_clicks_list, current_is_open_list, button_ids):
    ctx = callback_context
    if not ctx.triggered_id or not n_clicks_list: return current_is_open_list
    
    triggered_button_id_str = ctx.triggered_id.get("index") 
    if triggered_button_id_str is None: return current_is_open_list

    new_is_open_list = list(current_is_open_list)
    for i, button_id_dict in enumerate(button_ids):
        if str(button_id_dict.get("index")) == triggered_button_id_str and n_clicks_list[i] is not None:
            new_is_open_list[i] = not current_is_open_list[i]
            break
    return new_is_open_list

if __name__ == "__main__":
    # Your existing __main__ block for DB config check and app.run
    if not all([DB_CONFIG["dbname"], DB_CONFIG["user"], DB_CONFIG["password"], DB_CONFIG["host"]]):
        print("CRITICAL: Dashboard database configuration is incomplete. Set FLIPFORCE_POSTGRES_* env variables.")
        print(f"Loaded DB Config: {DB_CONFIG}")
    else:
        print(f"Dashboard starting with DB config: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']} (User: {DB_CONFIG['user']})")
        app.run(debug=True, host="0.0.0.0", port=8050)