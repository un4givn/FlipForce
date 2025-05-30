"""
Dash application for displaying FlipForce sold card events,
summarizing tier and series data.
"""
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context
import pandas as pd
import psycopg2

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server

# --- Configuration ---
DB_CONFIG = {
    "host": "flipforce-db",
    "port": 5432,
    "dbname": "flipforce",
    "user": "flipforce_user",
    "password": "flipforce_pass"
}

# --- Define Custom Sort Order ---
# This order is based on the provided image.
# IMPORTANT: The names in this list must EXACTLY MATCH the values stored in the
# 'pack_series_metadata.tier' column in your database (which is fetched as 'pack_category').
# Based on the API example ("Diamond"), these are likely TitleCased.
# If your database stores them as "DIAMOND", "EMERALD", etc., update this list accordingly.
PACK_CATEGORY_ORDER = ["Diamond", "Emerald", "Ruby", "Gold", "Silver", "Misc"]
# If "Misc." includes a period in your database, use "Misc." instead of "Misc".


# --- Data Fetching ---
def fetch_data():
    """
    Fetches sold card event data, including card tier, series_id,
    pack name, and pack category from the PostgreSQL database.

    Returns:
        pd.DataFrame: DataFrame with 'series_id', 'card_tier', 'pack_name', 'pack_category'.
                      Returns an empty DataFrame if the database fetch fails.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = """
        SELECT
            sce.series_id,
            sce.tier AS card_tier,
            psm.name AS pack_name,
            psm.tier AS pack_category
        FROM
            sold_card_events sce
        LEFT JOIN
            pack_series_metadata psm ON sce.series_id = psm.series_id;
        """
        all_df = pd.read_sql(query, conn)
        conn.close()
        return all_df
    except Exception as e:
        print(f"[ERROR] DB fetch failed: {e}")
        return pd.DataFrame()

# --- UI Component Generation ---
def make_series_cards(df_sorted_for_display): # DataFrame should be pre-sorted
    """
    Generates a list of Dash Bootstrap Card components, one for each series_id,
    in the order provided by the sorted DataFrame.

    Args:
        df_sorted_for_display (pd.DataFrame): Pre-sorted DataFrame with 'series_id',
                           'card_tier', 'pack_name', 'pack_category' columns.

    Returns:
        list: A list of dbc.Card components or an html.Div with an error message
              if the input DataFrame is empty.
    """
    if df_sorted_for_display.empty:
        return html.Div("No sold card data available to generate series cards.", className="text-danger")

    cards = []
    # Get unique series information, preserving the pre-sorted order
    unique_series_df = df_sorted_for_display.drop_duplicates(subset=['series_id'], keep='first')

    for _, row in unique_series_df.iterrows():
        series_id = row['series_id']
        pack_name_val = row['pack_name']
        pack_category_val = row['pack_category']

        # Filter the full (sorted) DataFrame for all records of the current series_id
        # to get correct total_sold and card_tier_counts
        group_df_for_series = df_sorted_for_display[df_sorted_for_display['series_id'] == series_id]

        # Construct the full display name
        display_pack_name = pack_name_val if pd.notna(pack_name_val) and pack_name_val else ""
        display_pack_category = pack_category_val if pd.notna(pack_category_val) and pack_category_val else ""

        if display_pack_category and display_pack_name:
            full_display_name = f"{display_pack_category} {display_pack_name}"
        elif display_pack_name:
            full_display_name = display_pack_name
        elif display_pack_category:
            full_display_name = display_pack_category
        else:
            full_display_name = series_id # Fallback to series_id

        total_sold = len(group_df_for_series)
        card_tier_counts = group_df_for_series["card_tier"].value_counts().to_dict()

        cards.append(
            dbc.Card([
                dbc.CardHeader(
                    dbc.Button(
                        f"{full_display_name} — {total_sold} Sold",
                        id={"type": "series-toggle", "index": series_id},
                        className="w-100 text-start",
                        color="secondary"
                    )
                ),
                dbc.Collapse(
                    dbc.CardBody([
                        html.H6("Card Tier Breakdown"),
                        html.Ul([html.Li(f"{tier}: {count}") for tier, count in card_tier_counts.items()])
                    ]),
                    id={"type": "series-collapse", "index": series_id},
                    is_open=False
                )
            ], className="mb-3 shadow-sm")
        )
    return cards

# --- Application Layout ---
app.layout = dbc.Container([
    dcc.Interval(id='initial-load-interval', interval=1, max_intervals=0),
    html.H2("📦 FlipForce Sold Tier + Series Summary", className="my-4"),
    dbc.Card([
        dbc.CardHeader(
            dbc.Button("Click to Expand Overall Card Tier Summary", id="tier-toggle", color="primary", className="w-100 text-start")
        ),
        dbc.Collapse(
            dbc.CardBody(id="tier-body"),
            id="tier-collapse",
            is_open=False
        )
    ], className="mb-4"),
    html.Div(id="series-card-container")
], fluid=True)

# --- Callbacks ---
@app.callback(
    Output("tier-body", "children"),
    Output("series-card-container", "children"),
    Input("initial-load-interval", "n_intervals")
)
def load_all_data(n_intervals):
    df = fetch_data()

    tier_summary_content = html.P("No card tier data to display.") # Default
    series_cards_content = html.Div("No sold card data available to generate series cards.", className="text-danger") # Default

    if not df.empty:
        # Apply custom sort order for pack categories
        if 'pack_category' in df.columns:
            # Create an ordered categorical type for sorting
            df['pack_category_ordered'] = pd.Categorical(
                df['pack_category'],
                categories=PACK_CATEGORY_ORDER,
                ordered=True
            )
            # Sort by the ordered pack category, then by pack name (alphabetical for sub-sorting),
            # and finally by series_id to ensure stable sort for packs with the same name (if any).
            # Categories not in PACK_CATEGORY_ORDER will be placed at the end due to na_position='last'.
            df.sort_values(
                by=['pack_category_ordered', 'pack_name', 'series_id'],
                inplace=True,
                na_position='last'
            )
        else:
            print("[WARN] 'pack_category' column not found for sorting. Cards may not be in desired order.")

        # Prepare overall card tier summary
        if "card_tier" in df.columns and not df["card_tier"].dropna().empty:
            tier_df = df["card_tier"].value_counts().reset_index()
            tier_df.columns = ["card_tier_name", "count"]
            tier_list_items = [html.Li(f"{row['card_tier_name']}: {row['count']}") for _, row in tier_df.iterrows()]
            tier_summary_content = html.Ul(tier_list_items)
        
        # Generate series cards using the now sorted DataFrame
        series_cards_content = make_series_cards(df)
    else:
        tier_summary_content = html.Div("No data available from the database.")
        series_cards_content = html.Div("Please check data source or connection.")


    return tier_summary_content, series_cards_content

@app.callback(
    Output("tier-collapse", "is_open"),
    Input("tier-toggle", "n_clicks"),
    State("tier-collapse", "is_open"),
    prevent_initial_call=True
)
def toggle_tier_summary_collapse(n_clicks, is_open):
    return not is_open

@app.callback(
    Output({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    Input({"type": "series-toggle", "index": dash.ALL}, "n_clicks"),
    State({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    State({"type": "series-toggle", "index": dash.ALL}, "id"),
    prevent_initial_call=True
)
def toggle_individual_series_collapse(n_clicks_list, current_is_open_list, button_ids):
    ctx = callback_context
    if not ctx.triggered_id:
        return current_is_open_list

    triggered_button_id_details = ctx.triggered_id
    triggered_button_index_value = triggered_button_id_details["index"]

    new_is_open_list = []
    for i, button_id_dict in enumerate(button_ids):
        if button_id_dict["index"] == triggered_button_index_value:
            new_is_open_list.append(not current_is_open_list[i])
        else:
            new_is_open_list.append(current_is_open_list[i])
            
    return new_is_open_list

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")