# dashboard/ui_components.py
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
from config import STATIC_PACK_COSTS_CENTS
from dash import dcc, html


def make_series_cards(base_series_df, hist_val_trend_data_for_graph, all_sold_cards_df, all_current_cards_df):
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
        
        series_specific_current_cards = (
            all_current_cards_df[all_current_cards_df["series_id"] == series_id]
            if not all_current_cards_df.empty
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
        min_hist_total_val_cents = row.get('min_historical_total_value_cents')
        max_hist_total_val_cents = row.get('max_historical_total_value_cents')

        min_hist_total_val_display = (
            f"${min_hist_total_val_cents / 100:.2f}"
            if pd.notna(min_hist_total_val_cents)
            else "N/A"
        )
        max_hist_total_val_display = (
            f"${max_hist_total_val_cents / 100:.2f}"
            if pd.notna(max_hist_total_val_cents)
            else "N/A"
        )
        
        cards_over_pack_price_count_val = row.get('cards_over_pack_price_count', 0)

        # Standard ROI/EV
        static_cost_val = row.get("static_pack_cost_cents")
        static_cost_display = (
            f"${static_cost_val / 100:.2f}" if pd.notna(static_cost_val) else "N/A"
        )
        current_ev_cents = row.get("expected_value_cents")
        current_roi_val = row.get("roi")
        current_ev_display = (
            f"${current_ev_cents / 100:.2f}" if pd.notna(current_ev_cents) else "N/A"
        )
        current_roi_display_str = (
            f"{current_roi_val:.2%}"
            if pd.notna(current_roi_val) and not (isinstance(current_roi_val, float) and np.isinf(current_roi_val))
            else "N/A"
        )
        min_hist_roi_val = row.get("min_historical_roi", np.nan)
        max_hist_roi_val = row.get("max_historical_roi", np.nan)
        min_hist_roi_display = (
            f"{min_hist_roi_val:.2%}"
            if pd.notna(min_hist_roi_val) and not (isinstance(min_hist_roi_val, float) and np.isinf(min_hist_roi_val))
            else "N/A"
        )
        max_hist_roi_display = (
            f"{max_hist_roi_val:.2%}"
            if pd.notna(max_hist_roi_val) and not (isinstance(max_hist_roi_val, float) and np.isinf(max_hist_roi_val))
            else "N/A"
        )

        # ROIBB / EVBB
        pack_cost_bb_cents_val = row.get("pack_cost_bb_cents")
        pack_cost_bb_display = (
            f"${pack_cost_bb_cents_val / 100:.2f}" if pd.notna(pack_cost_bb_cents_val) else "N/A"
        )
        current_ev_bb_cents_val = row.get("expected_value_bb_cents")
        current_ev_bb_display = (
            f"${current_ev_bb_cents_val / 100:.2f}" if pd.notna(current_ev_bb_cents_val) else "N/A"
        )
        current_roibb_val = row.get("roi_bb")
        current_roibb_display_str = (
            f"{current_roibb_val:.2%}"
            if pd.notna(current_roibb_val) and not (isinstance(current_roibb_val, float) and np.isinf(current_roibb_val))
            else "N/A"
        )
        min_hist_roibb_val = row.get("min_historical_roi_bb", np.nan)
        max_hist_roibb_val = row.get("max_historical_roi_bb", np.nan)
        min_hist_roibb_display = (
            f"{min_hist_roibb_val:.2%}"
            if pd.notna(min_hist_roibb_val) and not (isinstance(min_hist_roibb_val, float) and np.isinf(min_hist_roibb_val))
            else "N/A"
        )
        max_hist_roibb_display = (
            f"{max_hist_roibb_val:.2%}"
            if pd.notna(max_hist_roibb_val) and not (isinstance(max_hist_roibb_val, float) and np.isinf(max_hist_roibb_val))
            else "N/A"
        )

        psg_display = row.get("purchases_since_grail_str", "N/A")
        psc_display = row.get("purchases_since_chase_str", "N/A")

        full_display_name_card = (
            f"{pack_category_val} {pack_name_val}"
            if pack_category_val not in ["Unknown Category", None]
            else pack_name_val
        )

        # Determine ROI text color and component
        if current_roi_display_str != "N/A" and pd.notna(current_roi_val) and not (isinstance(current_roi_val, float) and np.isinf(current_roi_val)):
            if current_roi_val > 0:
                roi_color_class = "text-success fw-bold"  # Green and Bold
            elif current_roi_val >= -0.03:
                roi_color_class = "text-warning fw-bold"  # Orange and Bold
            else:
                roi_color_class = "text-danger fw-bold"   # Red and Bold
            colored_roi_text_component = html.Span(current_roi_display_str, className=roi_color_class)
        else:
            colored_roi_text_component = html.Span(current_roi_display_str, className="fw-bold")

        # Determine ROIBB text color and component
        if current_roibb_display_str != "N/A" and pd.notna(current_roibb_val) and not (isinstance(current_roibb_val, float) and np.isinf(current_roibb_val)):
            if current_roibb_val > 0:
                roibb_color_class = "text-success fw-bold"  # Green and Bold
            elif current_roibb_val >= -0.03:
                roibb_color_class = "text-warning fw-bold"  # Orange and Bold
            else:
                roibb_color_class = "text-danger fw-bold"   # Red and Bold
            colored_roibb_text_component = html.Span(current_roibb_display_str, className=roibb_color_class)
        else:
            colored_roibb_text_component = html.Span(current_roibb_display_str, className="fw-bold")


        button_header_children = [
            html.Span(f"{full_display_name_card} — ROI: "),
            colored_roi_text_component,
            html.Span(" (ROIBB: "),
            colored_roibb_text_component,
            html.Span(f") — EV: {current_ev_display} — COPP: {cards_over_pack_price_count_val}")
        ]
        
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
            dbc.Row(
                [
                    dbc.Col(html.P(f"Sales Since Last Grail: {psg_display}"), width=6),
                    dbc.Col(html.P(f"Sales Since Last Chase: {psc_display}"), width=6),
                ]
            ),
            html.H6("Card Tier Breakdown (Sold Hits)"),
            html.Ul(tier_summary_list_items),
            html.Hr(),
            html.H6("Pack Valuation Metrics (Standard)"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Standard Pack Cost: {static_cost_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Standard EV (per pack): {current_ev_display}"), width=6
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P([
                            html.Span("Standard ROI: "),
                            colored_roi_text_component 
                        ]),
                        width=6, 
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Hist. Min ROI: {min_hist_roi_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Hist. Max ROI: {max_hist_roi_display}"), width=6
                    ),
                ]
            ),
            html.Hr(),
            html.H6("Pack Valuation Metrics (With Buyback Floor)"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(f"Buyback Pack Cost (Cost +10%): {pack_cost_bb_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Buyback EV (Floor 80%): {current_ev_bb_display}"), width=6
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P([
                            html.Span("ROIBB (ROI with Buyback): "),
                            colored_roibb_text_component # Use the colored component here too
                        ]),
                        width=6, 
                    ),
                ]
            ),
            dbc.Row(
                [
                     dbc.Col(
                        html.P(f"Hist. Min ROIBB: {min_hist_roibb_display}"), width=6
                    ),
                    dbc.Col(
                        html.P(f"Hist. Max ROIBB: {max_hist_roibb_display}"), width=6
                    ),
                ]
            ),
            html.Hr(),
            html.H6("Pack Contents Value (Sum of all current cards)"),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(
                            "Current Total Available Value: "
                            f"{curr_total_avail_val_display}"
                        ),
                        width=6,
                    ),
                     dbc.Col(
                        html.P(
                            f"Cards > Pack Price: {cards_over_pack_price_count_val}"
                        ),
                        width=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.P(
                            "Historical Min Available Value: "
                            f"{min_hist_total_val_display}"
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        html.P(
                            "Historical Max Available Value: "
                            f"{max_hist_total_val_display}"
                        ),
                        width=6,
                    ),
                ]
            ),
        ]

        current_cards_display_list_ui = []
        if not series_specific_current_cards.empty:
            top_current_cards = series_specific_current_cards.sort_values(
                by="estimated_value_cents", ascending=False
            ).head(10)
            display_cols_for_current_cards = [
                "player_name", "tier", "overall", "insert_name", 
                "estimated_value_cents", "front_image",
            ]
            for _, card_row_curr in top_current_cards.iterrows():
                item_details_children_curr = []
                card_identifier_curr = card_row_curr.get("player_name", "")
                if pd.isna(card_identifier_curr) or str(card_identifier_curr).strip() == "":
                    card_identifier_curr = card_row_curr.get(
                        "insert_name", f"Card ID: {card_row_curr.get('card_id', 'Unknown')}"
                    )
                else:
                    insert_name_val_curr = card_row_curr.get("insert_name")
                    if pd.notna(insert_name_val_curr) and str(insert_name_val_curr).strip() != "":
                        card_identifier_curr += f" - {insert_name_val_curr}"
                
                item_details_children_curr.append(html.Strong(card_identifier_curr))
                list_items_for_card_display_curr = []
                for col_current in display_cols_for_current_cards:
                    if col_current in card_row_curr:
                        value_curr = card_row_curr[col_current]
                        col_display_name_current = col_current.replace("_", " ").title()
                        if pd.isna(value_curr) or (isinstance(value_curr, str) and value_curr.strip() == ""):
                            value_display_curr = html.Em("N/A")
                        elif col_current == "estimated_value_cents":
                            value_display_curr = (
                                f"${value_curr / 100:.2f}" if pd.notna(value_curr) else html.Em("N/A")
                            )
                        elif col_current == "overall" and pd.notna(value_curr):
                             value_display_curr = f"{int(value_curr)}"
                        elif (
                            col_current == "front_image"
                            and pd.notna(value_curr)
                            and "http" in str(value_curr).lower()
                        ):
                            value_display_curr = html.A(
                                "Image", href=str(value_curr), target="_blank", style={"fontSize": "0.8em"},
                            )
                        else:
                            value_display_curr = str(value_curr)
                        list_items_for_card_display_curr.append(
                            html.Li(
                                [
                                    html.Span(f"{col_display_name_current}: ", style={"fontWeight": "500"}),
                                    value_display_curr,
                                ],
                                style={"lineHeight": "1.4", "fontSize": "0.85rem"},
                            )
                        )
                item_details_children_curr.append(
                    html.Ul(
                        list_items_for_card_display_curr,
                        style={
                            "fontSize": "0.8rem", "paddingLeft": "15px", 
                            "listStyleType": "disc", "marginBottom": "3px",
                        },
                    )
                )
                current_cards_display_list_ui.append(
                    dbc.ListGroupItem(item_details_children_curr, style={"padding": "0.5rem 0.7rem"})
                )
            
            current_cards_scrolling_div_content = dbc.ListGroup(current_cards_display_list_ui, flush=True)
            card_body_items.extend([
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6("Currently Available Cards (Top 10 by Value)", style={"marginTop": "0.5rem", "marginBottom": "0.5rem"}),
                html.Div(
                    current_cards_scrolling_div_content,
                    style={
                        "maxHeight": "300px", "overflowY": "auto", "border": "1px solid #eee",
                        "padding": "0px", "marginTop": "10px",
                    },
                ),
            ])
        else:
            card_body_items.extend([
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.P(html.Em("No currently available cards data for this series."))
            ])

        if total_sold_for_this_series > 0:
            sold_cards_display_list_ui = []
            display_cols_for_sold_cards = [
                "player_name", "card_tier", "overall", "insert_name",
                "sold_card_value_cents", "sold_at", "front_image",
            ]
            for _, card_event_row in series_specific_sold_events.head(10).iterrows():
                item_details_children_sold = []
                card_identifier_sold = card_event_row.get("player_name", "")
                if pd.isna(card_identifier_sold) or str(card_identifier_sold).strip() == "":
                    card_identifier_sold = card_event_row.get(
                        "insert_name", f"Card ID: {card_event_row.get('card_id', 'Unknown')}",
                    )
                else:
                    insert_name_val_sold = card_event_row.get("insert_name")
                    if pd.notna(insert_name_val_sold) and str(insert_name_val_sold).strip() != "":
                        card_identifier_sold += f" - {insert_name_val_sold}"

                item_details_children_sold.append(html.Strong(card_identifier_sold))
                list_items_for_card_display_sold = []
                for col_sold in display_cols_for_sold_cards:
                    if col_sold in card_event_row:
                        value_sold = card_event_row[col_sold]
                        col_display_name_sold = col_sold.replace("_", " ").title()
                        if pd.isna(value_sold) or (isinstance(value_sold, str) and value_sold.strip() == ""):
                            value_display_sold = html.Em("N/A")
                        elif col_sold == "sold_at":
                            value_display_sold = (
                                pd.to_datetime(value_sold).strftime("%Y-%m-%d %H:%M")
                                if pd.notna(value_sold) else html.Em("N/A")
                            )
                        elif col_sold == "sold_card_value_cents":
                            value_display_sold = (
                                f"${value_sold / 100:.2f}" if pd.notna(value_sold) else html.Em("N/A")
                            )
                        elif col_sold == "overall" and pd.notna(value_sold):
                            value_display_sold = f"{int(value_sold)}"
                        elif (col_sold == "front_image" and pd.notna(value_sold) and "http" in str(value_sold).lower()):
                            value_display_sold = html.A(
                                "Image", href=str(value_sold), target="_blank", style={"fontSize": "0.8em"},
                            )
                        else:
                            value_display_sold = str(value_sold)
                        list_items_for_card_display_sold.append(
                            html.Li(
                                [
                                    html.Span(f"{col_display_name_sold}: ", style={"fontWeight": "500"}),
                                    value_display_sold,
                                ],
                                style={"lineHeight": "1.4", "fontSize": "0.85rem"},
                            )
                        )
                item_details_children_sold.append(
                    html.Ul(
                        list_items_for_card_display_sold,
                        style={
                            "fontSize": "0.8rem", "paddingLeft": "15px",
                            "listStyleType": "disc", "marginBottom": "3px",
                        },
                    )
                )
                sold_cards_display_list_ui.append(
                    dbc.ListGroupItem(item_details_children_sold, style={"padding": "0.5rem 0.7rem"})
                )
            
            sold_cards_scrolling_div_content = dbc.ListGroup(sold_cards_display_list_ui, flush=True)
            card_body_items.extend([
                html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}),
                html.H6("Recently Sold Card Details (Max 10 shown)", style={"marginTop": "0.5rem", "marginBottom": "0.5rem"}),
                html.Div(
                    sold_cards_scrolling_div_content,
                    style={
                        "maxHeight": "300px", "overflowY": "auto", "border": "1px solid #eee",
                        "padding": "0px", "marginTop": "10px",
                    },
                ),
            ])

        else:
            card_body_items.extend(
                [html.Hr(style={"marginTop": "1rem", "marginBottom": "1rem"}), html.P(html.Em("No sales recorded for this series yet."))]
            )

        graph_figure_component = html.Em("Not enough data to plot pack value trend.")
        if (
            hist_val_trend_data_for_graph is not None
            and not hist_val_trend_data_for_graph.empty
        ):
            series_hist_val_for_graph = hist_val_trend_data_for_graph[
                hist_val_trend_data_for_graph["series_id"] == series_id
            ].copy()
            if (not series_hist_val_for_graph.empty and len(series_hist_val_for_graph) > 1):
                series_hist_val_for_graph["total_pack_value_dollars"] = (
                    series_hist_val_for_graph["total_estimated_value_cents"] / 100.0
                )
                fig = px.line(
                    series_hist_val_for_graph, x="snapshot_time", y="total_pack_value_dollars",
                    labels={"snapshot_time": "Date", "total_pack_value_dollars": "Total Value ($)"},
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10), height=200,
                    yaxis_title="Value ($)", xaxis_title=None, showlegend=False, font=dict(size=10),
                )
                graph_figure_component = dcc.Graph(figure=fig, config={"displayModeBar": False})
            elif not series_hist_val_for_graph.empty:
                graph_figure_component = html.Em("Only one data point for total pack value trend.")

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
                            button_header_children,
                            id={"type": "series-toggle", "index": str(series_id)},
                            className="w-100 text-start",
                            color="light", 
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