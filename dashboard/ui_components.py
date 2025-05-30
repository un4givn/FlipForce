# dashboard/ui_components.py
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
from config import STATIC_PACK_COSTS_CENTS  # Import from config.py
from dash import dcc, html


def make_series_cards(base_series_df, hist_val_trend_data_for_graph, all_sold_cards_df):
    """
    Generates a list of Dash Bootstrap Components (dbc) Cards for each series.
    base_series_df is expected to be pre-merged with latest total values, EV/ROI, and historical min/max for these.
    all_sold_cards_df is the raw result from fetch_sold_cards_and_pack_metadata.
    """
    if base_series_df.empty:
        return html.Div(
            "No series data available to generate cards.", className="text-info"
        )
    if "series_id" not in base_series_df.columns:
        return html.Div(
            "Essential 'series_id' column missing from display data.",
            className="text-danger",
        )

    cards = []
    unique_series_display_df = base_series_df

    for _, row in unique_series_display_df.iterrows():
        series_id = row["series_id"]
        pack_name_val = row.get("pack_name", "N/A")
        pack_category_val = row.get("pack_category", "Unknown Category")

        series_specific_sold_events = (
            all_sold_cards_df[
                (all_sold_cards_df["series_id"] == series_id)
                & (all_sold_cards_df["event_id"].notna())
            ]
            if not all_sold_cards_df.empty
            else pd.DataFrame()
        )

        total_sold_for_this_series = len(series_specific_sold_events)

        tier_summary_list_items = []
        if (
            total_sold_for_this_series > 0
            and "card_tier" in series_specific_sold_events.columns
        ):
            card_tier_counts = series_specific_sold_events["card_tier"].value_counts()
            for tier, count in card_tier_counts.items():
                percentage = (count / total_sold_for_this_series) * 100
                tier_display_name = tier if pd.notna(tier) else "Unspecified Tier"
                tier_summary_list_items.append(
                    html.Li(f"{tier_display_name}: {count} ({percentage:.1f}%)")
                )
        else:
            tier_summary_list_items.append(
                html.Li("No sales data for tier breakdown for this series.")
            )

        avg_sold_val_cents = (
            series_specific_sold_events["sold_card_value_cents"].mean()
            if total_sold_for_this_series > 0
            else np.nan
        )
        avg_sold_val_display = (
            f"${avg_sold_val_cents / 100:.2f}"
            if pd.notna(avg_sold_val_cents)
            else "N/A"
        )

        curr_total_avail_val_cents = row.get("current_total_available_value_cents")
        curr_total_avail_val_display = (
            f"${curr_total_avail_val_cents / 100:.2f}"
            if pd.notna(curr_total_avail_val_cents)
            else "N/A"
        )

        min_hist_total_val_display = (
            f"${row.get('min_historical_total_value_cents', np.nan) / 100:.2f}"
            if pd.notna(row.get("min_historical_total_value_cents"))
            else "N/A"
        )
        max_hist_total_val_display = (
            f"${row.get('max_historical_total_value_cents', np.nan) / 100:.2f}"
            if pd.notna(row.get("max_historical_total_value_cents"))
            else "N/A"
        )

        static_cost_val = STATIC_PACK_COSTS_CENTS.get(pack_category_val)
        static_cost_display = (
            f"${static_cost_val / 100:.2f}" if static_cost_val is not None else "N/A"
        )

        current_ev_cents = row.get("expected_value_cents")
        current_roi_val = row.get("roi")
        current_ev_display = (
            f"${current_ev_cents / 100:.2f}" if pd.notna(current_ev_cents) else "N/A"
        )
        current_roi_display = (
            f"{current_roi_val:.2%}"
            if pd.notna(current_roi_val)
            and current_roi_val is not None
            and not (isinstance(current_roi_val, float) and np.isinf(current_roi_val))
            else "N/A"
        )

        min_hist_roi_val = row.get("min_historical_roi", np.nan)
        max_hist_roi_val = row.get("max_historical_roi", np.nan)
        min_hist_roi_display = (
            f"{min_hist_roi_val:.2%}"
            if pd.notna(min_hist_roi_val)
            and not (isinstance(min_hist_roi_val, float) and np.isinf(min_hist_roi_val))
            else "N/A"
        )
        max_hist_roi_display = (
            f"{max_hist_roi_val:.2%}"
            if pd.notna(max_hist_roi_val)
            and not (isinstance(max_hist_roi_val, float) and np.isinf(max_hist_roi_val))
            else "N/A"
        )

        full_display_name_card = (
            f"{pack_category_val} {pack_name_val}"
            if pack_category_val not in ["Unknown Category", None]
            else pack_name_val
        )
        button_header_text = f"{full_display_name_card} — ROI: {current_roi_display} — EV: {current_ev_display}"

        card_body_items = [
            html.H6("Sales Summary", className="mt-2"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Total Sold Cards: {total_sold_for_this_series}"),
                        width=6,
                    ),
                    dbc.Col(
                        html.P(f"Avg. Sold Card Value: {avg_sold_val_display}"), width=6
                    ),
                ]
            ),
            html.H6("Card Tier Breakdown (Sold Hits)"),
            html.Ul(tier_summary_list_items),
            html.Hr(),
            html.H6("Pack Valuation Metrics"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Static Pack Cost: {static_cost_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Current EV (per pack): {current_ev_display}"), width=6
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Current ROI (vs Static Cost): {current_roi_display}"),
                        width=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Historical Min ROI: {min_hist_roi_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Historical Max ROI: {max_hist_roi_display}"), width=6
                    ),
                ]
            ),
            html.Hr(),
            html.H6("Pack Contents Value (Sum of all current cards)"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(
                            f"Current Total Available Value: {curr_total_avail_val_display}"
                        ),
                        width=12,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(
                            f"Historical Min Available Value: {min_hist_total_val_display}"
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        html.P(
                            f"Historical Max Available Value: {max_hist_total_val_display}"
                        ),
                        width=6,
                    ),
                ]
            ),
        ]

        if total_sold_for_this_series > 0:
            sold_cards_display_list_ui = []
            display_cols_for_sold_cards = [
                "player_name",
                "card_tier",
                "overall",
                "insert_name",
                "sold_card_value_cents",
                "sold_at",
                "front_image",
            ]
            for _, card_event_row in series_specific_sold_events.head(10).iterrows():
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
                list_items_for_card_display = []
                for col_sold in display_cols_for_sold_cards:
                    if col_sold in card_event_row:
                        value = card_event_row[col_sold]
                        col_display_name_sold = col_sold.replace("_", " ").title()
                        if pd.isna(value) or (
                            isinstance(value, str) and value.strip() == ""
                        ):
                            value_display = html.Em("N/A")
                        elif col_sold == "sold_at":
                            value_display = (
                                pd.to_datetime(value).strftime("%Y-%m-%d %H:%M")
                                if pd.notna(value)
                                else html.Em("N/A")
                            )
                        elif col_sold == "sold_card_value_cents":
                            value_display = (
                                f"${value / 100:.2f}"
                                if pd.notna(value)
                                else html.Em("N/A")
                            )
                        elif col_sold == "overall" and pd.notna(value):
                            value_display = f"{int(value)}"
                        elif (
                            col_sold == "front_image"
                            and pd.notna(value)
                            and "http" in str(value).lower()
                        ):
                            value_display = html.A(
                                "Image",
                                href=str(value),
                                target="_blank",
                                style={"fontSize": "0.8em"},
                            )
                        else:
                            value_display = str(value)
                        list_items_for_card_display.append(
                            html.Li(
                                [
                                    html.Span(
                                        f"{col_display_name_sold}: ",
                                        style={"fontWeight": "500"},
                                    ),
                                    value_display,
                                ],
                                style={"lineHeight": "1.4", "fontSize": "0.85rem"},
                            )
                        )
                item_details_children.append(
                    html.Ul(
                        list_items_for_card_display,
                        style={
                            "fontSize": "0.8rem",
                            "paddingLeft": "15px",
                            "listStyleType": "disc",
                            "marginBottom": "3px",
                        },
                    )
                )
                sold_cards_display_list_ui.append(
                    dbc.ListGroupItem(
                        item_details_children, style={"padding": "0.5rem 0.7rem"}
                    )
                )

            sold_cards_scrolling_div_content = dbc.ListGroup(
                sold_cards_display_list_ui, flush=True
            )
            card_body_items.extend(
                [
                    html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                    html.H6(
                        "Recently Sold Card Details (Max 10 shown)",
                        style={"marginTop": "0.5rem", "marginBottom": "0.5rem"},
                    ),
                    html.Div(
                        sold_cards_scrolling_div_content,
                        style={
                            "maxHeight": "300px",
                            "overflowY": "auto",
                            "border": "1px solid #eee",
                            "padding": "0px",
                            "marginTop": "10px",
                        },
                    ),
                ]
            )
        else:
            card_body_items.extend(
                [html.Hr(), html.P(html.Em("No sales recorded for this series yet."))]
            )

        graph_figure_component = html.Em("Not enough data to plot pack value trend.")
        if (
            hist_val_trend_data_for_graph is not None
            and not hist_val_trend_data_for_graph.empty
        ):
            series_hist_val_for_graph = hist_val_trend_data_for_graph[
                hist_val_trend_data_for_graph["series_id"] == series_id
            ].copy()
            if (
                not series_hist_val_for_graph.empty
                and len(series_hist_val_for_graph) > 1
            ):
                series_hist_val_for_graph["total_pack_value_dollars"] = (
                    series_hist_val_for_graph["total_estimated_value_cents"] / 100.0
                )
                fig = px.line(
                    series_hist_val_for_graph,
                    x="snapshot_time",
                    y="total_pack_value_dollars",
                    labels={
                        "snapshot_time": "Date",
                        "total_pack_value_dollars": "Total Value ($)",
                    },
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=200,
                    yaxis_title="Value ($)",
                    xaxis_title=None,
                    showlegend=False,
                    font=dict(size=10),
                )
                graph_figure_component = dcc.Graph(
                    figure=fig, config={"displayModeBar": False}
                )
            elif not series_hist_val_for_graph.empty:
                graph_figure_component = html.Em(
                    "Only one data point for total pack value trend."
                )

        card_body_items.extend(
            [
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6(
                    "Historical Total Available Pack Value Trend",
                    style={"marginTop": "0.5rem", "marginBottom": "0.5rem"},
                ),
                graph_figure_component,
            ]
        )

        cards.append(
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Button(
                            button_header_text,
                            id={"type": "series-toggle", "index": str(series_id)},
                            className="w-100 text-start",
                            color="info",
                        )
                    ),
                    dbc.Collapse(
                        dbc.CardBody(html.Div(card_body_items)),
                        id={"type": "series-collapse", "index": str(series_id)},
                        is_open=False,
                    ),
                ],
                className="mb-3 shadow-sm",
            )
        )
    return (
        cards
        if cards
        else html.Div(
            "No series information processed for display.", className="text-warning"
        )
    )
