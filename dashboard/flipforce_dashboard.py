import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import pandas as pd
import psycopg2
import os

def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "flipforce"),
        user=os.getenv("POSTGRES_USER", "flipforce_user"),
        password=os.getenv("POSTGRES_PASSWORD", "flipforce_pass"),
        host=os.getenv("POSTGRES_HOST", "flipforce-db"),
        port=os.getenv("POSTGRES_PORT", 5432)
    )

def fetch_sold_cards():
    try:
        conn = get_conn()
        query = (
            "SELECT player_name, estimated_value_cents, sold_at, grading_company, insert_name "
            "FROM sold_card_events "
            "ORDER BY sold_at DESC "
            "LIMIT 1000;"
        )
        df = pd.read_sql(query, conn)
        conn.close()
        if df.empty:
            print("[Dashboard] ⚠️ No sold cards returned.")
        df["estimated_value_dollars"] = df["estimated_value_cents"] / 100.0
        return df
    except Exception as e:
        print("[Dashboard] ❌ DB query failed:", e)
        return pd.DataFrame()

app = dash.Dash(__name__)
app.title = "FlipForce Sold Card Dashboard"

app.layout = html.Div([
    html.H1("🃏 FlipForce: Sold Cards Overview", style={"textAlign": "center"}),
    dcc.Dropdown(id="player-filter", placeholder="Filter by Player", multi=True),
    dcc.Graph(id="sales-over-time"),
    dcc.Graph(id="value-by-player")
])

@app.callback(
    Output("player-filter", "options"),
    Input("sales-over-time", "id")
)
def populate_player_filter(_):
    df = fetch_sold_cards()
    unique_players = df["player_name"].dropna().unique()
    return [{"label": name, "value": name} for name in sorted(unique_players)]

@app.callback(
    Output("sales-over-time", "figure"),
    Output("value-by-player", "figure"),
    Input("player-filter", "value")
)
def update_graphs(selected_players):
    df = fetch_sold_cards()
    if selected_players:
        df = df[df["player_name"].isin(selected_players)]
    if df.empty:
        return px.line(title="No sales data to display."), px.bar(title="No value data to display.")

    try:
        time_chart = px.line(
            df.sort_values("sold_at"),
            x="sold_at",
            y="estimated_value_dollars",
            color="player_name",
            title="📈 Estimated Value of Sold Cards Over Time"
        )
    except Exception as e:
        print("[Dashboard] ❌ Failed to build time chart:", e)
        time_chart = px.line(title="Error in time chart.")

    try:
        bar_chart = px.bar(
            df.groupby("player_name")["estimated_value_dollars"].sum().nlargest(10).reset_index(),
            x="player_name",
            y="estimated_value_dollars",
            title="💰 Top 10 Players by Total Estimated Sale Value"
        )
    except Exception as e:
        print("[Dashboard] ❌ Failed to build bar chart:", e)
        bar_chart = px.bar(title="Error in bar chart.")

    return time_chart, bar_chart

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
