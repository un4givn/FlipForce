# dashboard/ui_components.py
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, html
from config import COLORS, ROI_THRESHOLDS # Import new color and threshold configs

def get_roi_styles(roi_value):
    """Determines the style for ROI display based on its value."""
    base_style = {
        "padding": "0.25rem 0.5rem",
        "borderRadius": "0.25rem",
        "fontWeight": "bold",
        "display": "inline-block", # Ensures background covers only text
        "marginRight": "5px", # Spacing between ROI and ROIBB
    }
    if pd.isna(roi_value) or (isinstance(roi_value, float) and np.isinf(roi_value)):
        return {"text": "N/A", "style": {**base_style, "color": COLORS["text"], "backgroundColor": COLORS["secondary"]}}
    
    roi_str = f"{roi_value:.2%}"
    if roi_value > ROI_THRESHOLDS["positive"]:
        return {"text": roi_str, "style": {**base_style, "color": COLORS["positive_roi_fg"], "backgroundColor": COLORS["positive_roi_bg"]}}
    elif roi_value >= ROI_THRESHOLDS["warning"]:
        return {"text": roi_str, "style": {**base_style, "color": COLORS["warning_roi_fg"], "backgroundColor": COLORS["warning_roi_bg"]}}
    else:
        return {"text": roi_str, "style": {**base_style, "color": COLORS["negative_roi_fg"], "backgroundColor": COLORS["negative_roi_bg"]}}

def create_metric_display(label, value, unit_prefix="", unit_suffix=""):
    """Helper function to create a consistent display for metrics."""
    return html.Div([
        html.Span(f"{label}: ", className="fw-normal me-1", style={"color": COLORS["text"]}),
        html.Span(f"{unit_prefix}{value}{unit_suffix}", className="fw-bold", style={"color": COLORS["primary"]})
    ], className="mb-1")


def make_series_cards(base_series_df, hist_val_trend_data_for_graph, all_sold_cards_df, all_current_cards_df):
    if base_series_df.empty:
        return html.Div("No series data available.", className="text-info text-center p-3")
    if "series_id" not in base_series_df.columns:
        return html.Div("Essential 'series_id' column missing.", className="text-danger text-center p-3")

    cards_accordion_items = []

    for _, row in base_series_df.iterrows():
        series_id = row["series_id"]
        pack_name_val = row.get("pack_name", "N/A")
        pack_category_val = row.get("pack_category", "Unknown Category")
        full_display_name_card = f"{pack_category_val} {pack_name_val}" if pack_category_val not in ["Unknown Category", None] else pack_name_val

        # ROI and EV data
        current_roi_val = row.get("roi")
        current_roibb_val = row.get("roi_bb")
        current_ev_cents = row.get("expected_value_cents")
        cards_over_pack_price_count_val = row.get('cards_over_pack_price_count', 0)

        roi_styled = get_roi_styles(current_roi_val)
        roibb_styled = get_roi_styles(current_roibb_val)
        
        current_ev_display = f"${current_ev_cents / 100:.2f}" if pd.notna(current_ev_cents) else "N/A"

        # Card Header Content
        card_header_content = html.Div([
            html.H5(full_display_name_card, className="mb-0 me-3 d-inline-block", style={"color": COLORS["primary"]}),
            html.Span(roi_styled["text"], style=roi_styled["style"]),
            html.Span(roibb_styled["text"], style=roibb_styled["style"]),
            html.Span(f"EV: {current_ev_display}", className="ms-2 me-2 fw-bold", style={"color": COLORS["text"]}),
            html.Span(f"COPP: {cards_over_pack_price_count_val}", className="fw-bold", style={"color": COLORS["text"]})
        ], className="d-flex align-items-center")

        # --- Card Body Content ---
        card_body_children = []

        # Sales Summary Section
        series_specific_sold_events = all_sold_cards_df[(all_sold_cards_df["series_id"] == series_id) & (all_sold_cards_df["event_id"].notna())] if not all_sold_cards_df.empty else pd.DataFrame()
        total_sold_for_this_series = len(series_specific_sold_events)
        avg_sold_val_cents = series_specific_sold_events["sold_card_value_cents"].mean() if total_sold_for_this_series > 0 else np.nan
        avg_sold_val_display = f"${avg_sold_val_cents / 100:.2f}" if pd.notna(avg_sold_val_cents) else "N/A"
        psg_display = row.get("purchases_since_grail_str", "N/A")
        psc_display = row.get("purchases_since_chase_str", "N/A")

        sales_summary_section = dbc.Col([
            html.H6("Sales Summary", className="text-decoration-underline mb-2", style={"color": COLORS["text"]}),
            create_metric_display("Total Sold Cards", total_sold_for_this_series),
            create_metric_display("Avg. Sold Value", avg_sold_val_display),
            create_metric_display("Sales Since Grail", psg_display),
            create_metric_display("Sales Since Chase", psc_display),
        ], md=6, className="mb-3")

        # Card Tier Breakdown Section
        tier_summary_list_items_ui = []
        if total_sold_for_this_series > 0 and "card_tier" in series_specific_sold_events.columns:
            card_tier_counts = series_specific_sold_events["card_tier"].value_counts()
            for tier, count in card_tier_counts.items():
                percentage = (count / total_sold_for_this_series) * 100
                tier_display_name = tier if pd.notna(tier) else "Unspecified"
                tier_summary_list_items_ui.append(html.Li(f"{tier_display_name}: {count} ({percentage:.1f}%)", style={"color": COLORS["text"]}))
        else:
            tier_summary_list_items_ui.append(html.Li("No sales data for tier breakdown.", style={"color": COLORS["text"]}))
        
        tier_breakdown_section = dbc.Col([
            html.H6("Card Tier Breakdown (Sold Hits)", className="text-decoration-underline mb-2", style={"color": COLORS["text"]}),
            html.Ul(tier_summary_list_items_ui, className="list-unstyled ps-0")
        ], md=6, className="mb-3")
        
        card_body_children.append(dbc.Row([sales_summary_section, tier_breakdown_section]))
        card_body_children.append(html.Hr(style={"borderColor": COLORS["border_color"]}))

        # Pack Valuation Metrics (Standard)
        static_cost_val = row.get("static_pack_cost_cents")
        static_cost_display = f"${static_cost_val / 100:.2f}" if pd.notna(static_cost_val) else "N/A"
        min_hist_roi_val = row.get("min_historical_roi", np.nan)
        max_hist_roi_val = row.get("max_historical_roi", np.nan)
        min_hist_roi_styled = get_roi_styles(min_hist_roi_val)
        max_hist_roi_styled = get_roi_styles(max_hist_roi_val)

        standard_valuation_section = dbc.Col([
            html.H6("Pack Valuation (Standard)", className="text-decoration-underline mb-2", style={"color": COLORS["text"]}),
            create_metric_display("Pack Cost", static_cost_display),
            create_metric_display("EV (per pack)", current_ev_display),
            html.Div([html.Span("ROI: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(roi_styled["text"], style=roi_styled["style"])], className="mb-1"),
            html.Div([html.Span("Hist. Min ROI: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(min_hist_roi_styled["text"], style=min_hist_roi_styled["style"])], className="mb-1"),
            html.Div([html.Span("Hist. Max ROI: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(max_hist_roi_styled["text"], style=max_hist_roi_styled["style"])], className="mb-1"),
        ], md=6, className="mb-3")

        # Pack Valuation Metrics (Buyback Floor)
        pack_cost_bb_cents_val = row.get("pack_cost_bb_cents")
        pack_cost_bb_display = f"${pack_cost_bb_cents_val / 100:.2f}" if pd.notna(pack_cost_bb_cents_val) else "N/A"
        current_ev_bb_cents_val = row.get("expected_value_bb_cents")
        current_ev_bb_display = f"${current_ev_bb_cents_val / 100:.2f}" if pd.notna(current_ev_bb_cents_val) else "N/A"
        min_hist_roibb_val = row.get("min_historical_roi_bb", np.nan)
        max_hist_roibb_val = row.get("max_historical_roi_bb", np.nan)
        min_hist_roibb_styled = get_roi_styles(min_hist_roibb_val)
        max_hist_roibb_styled = get_roi_styles(max_hist_roibb_val)

        buyback_valuation_section = dbc.Col([
            html.H6("Pack Valuation (Buyback Floor)", className="text-decoration-underline mb-2", style={"color": COLORS["text"]}),
            create_metric_display("Buyback Pack Cost", pack_cost_bb_display),
            create_metric_display("Buyback EV", current_ev_bb_display),
            html.Div([html.Span("ROIBB: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(roibb_styled["text"], style=roibb_styled["style"])], className="mb-1"),
            html.Div([html.Span("Hist. Min ROIBB: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(min_hist_roibb_styled["text"], style=min_hist_roibb_styled["style"])], className="mb-1"),
            html.Div([html.Span("Hist. Max ROIBB: ", className="fw-normal me-1", style={"color": COLORS["text"]}), html.Span(max_hist_roibb_styled["text"], style=max_hist_roibb_styled["style"])], className="mb-1"),
        ], md=6, className="mb-3")

        card_body_children.append(dbc.Row([standard_valuation_section, buyback_valuation_section]))
        card_body_children.append(html.Hr(style={"borderColor": COLORS["border_color"]}))
        
        # Pack Contents Value Section
        curr_total_avail_val_cents = row.get("current_total_available_value_cents")
        curr_total_avail_val_display = f"${curr_total_avail_val_cents / 100:.2f}" if pd.notna(curr_total_avail_val_cents) else "N/A"
        min_hist_total_val_cents = row.get('min_historical_total_value_cents')
        max_hist_total_val_cents = row.get('max_historical_total_value_cents')
        min_hist_total_val_display = f"${min_hist_total_val_cents / 100:.2f}" if pd.notna(min_hist_total_val_cents) else "N/A"
        max_hist_total_val_display = f"${max_hist_total_val_cents / 100:.2f}" if pd.notna(max_hist_total_val_cents) else "N/A"

        pack_contents_section = dbc.Col([
            html.H6("Pack Contents Value (Sum of current cards)", className="text-decoration-underline mb-2", style={"color": COLORS["text"]}),
            create_metric_display("Current Total Value", curr_total_avail_val_display),
            create_metric_display("Cards > Pack Price", cards_over_pack_price_count_val),
            create_metric_display("Hist. Min Value", min_hist_total_val_display),
            create_metric_display("Hist. Max Value", max_hist_total_val_display),
        ], md=12, className="mb-3") # Full width for this section
        card_body_children.append(dbc.Row([pack_contents_section]))
        
        # Historical Value Trend Graph
        graph_figure_component = html.Em("Not enough data for trend.", style={"color": COLORS["text"]})
        if hist_val_trend_data_for_graph is not None and not hist_val_trend_data_for_graph.empty:
            series_hist_val_for_graph = hist_val_trend_data_for_graph[hist_val_trend_data_for_graph["series_id"] == series_id].copy()
            if not series_hist_val_for_graph.empty and len(series_hist_val_for_graph) > 1:
                series_hist_val_for_graph["total_pack_value_dollars"] = series_hist_val_for_graph["total_estimated_value_cents"] / 100.0
                fig = px.line(
                    series_hist_val_for_graph, x="snapshot_time", y="total_pack_value_dollars",
                    labels={"snapshot_time": "Date", "total_pack_value_dollars": "Total Value ($)"},
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10), height=250,
                    yaxis_title="Value ($)", xaxis_title=None, showlegend=False, font=dict(size=10, color=COLORS["text"]),
                    paper_bgcolor=COLORS["card_background"], plot_bgcolor=COLORS["card_background"],
                    xaxis=dict(gridcolor=COLORS["border_color"]), yaxis=dict(gridcolor=COLORS["border_color"])
                )
                graph_figure_component = dcc.Graph(figure=fig, config={"displayModeBar": False})
            elif not series_hist_val_for_graph.empty:
                 graph_figure_component = html.Em("Only one data point for trend.", style={"color": COLORS["text"]})
        
        card_body_children.append(html.Hr(style={"borderColor": COLORS["border_color"]}))
        card_body_children.append(html.H6("Historical Total Available Pack Value Trend", className="mb-2", style={"color": COLORS["text"]}))
        card_body_children.append(graph_figure_component)


        # Available and Sold Cards Lists
        def create_card_list_item(card_row_data, type_is_sold=False):
            card_identifier = card_row_data.get("player_name", "")
            if pd.isna(card_identifier) or str(card_identifier).strip() == "":
                card_identifier = card_row_data.get("insert_name", f"Card ID: {card_row_data.get('card_id', 'Unknown')}")
            else:
                insert_name_val = card_row_data.get("insert_name")
                if pd.notna(insert_name_val) and str(insert_name_val).strip() != "":
                    card_identifier += f" - {insert_name_val}"
            
            value_cents_col = "sold_card_value_cents" if type_is_sold else "estimated_value_cents"
            value_display = f"${card_row_data.get(value_cents_col, 0) / 100:.2f}"

            tier_display = card_row_data.get("tier" if not type_is_sold else "card_tier", "N/A")
            overall_display = f"OVR: {int(card_row_data.get('overall', 0))}" if pd.notna(card_row_data.get('overall')) else ""
            
            image_url = card_row_data.get("front_image")
            image_link = html.A("Img", href=image_url, target="_blank", className="badge bg-secondary text-decoration-none ms-1") if pd.notna(image_url) and "http" in str(image_url).lower() else ""

            sold_at_display = ""
            if type_is_sold and pd.notna(card_row_data.get("sold_at")):
                sold_at_display = f"Sold: {pd.to_datetime(card_row_data['sold_at']).strftime('%m/%d %H:%M')}"


            return dbc.ListGroupItem([
                html.Div([
                    html.Strong(f"{card_identifier} ({value_display})", style={"color": COLORS["primary"]}),
                    image_link
                ], className="d-flex justify-content-between align-items-center"),
                html.Small(f"Tier: {tier_display} {overall_display} {sold_at_display}".strip(), style={"color": COLORS["text"]})
            ], style={"backgroundColor": COLORS["card_background"], "borderColor": COLORS["border_color"], "padding": "0.5rem 0.75rem"})

        # Current Cards
        current_cards_list_ui = [html.P(html.Em("No current cards data for this series."), style={"color": COLORS["text"]})]
        series_specific_current_cards = all_current_cards_df[all_current_cards_df["series_id"] == series_id] if not all_current_cards_df.empty else pd.DataFrame()
        if not series_specific_current_cards.empty:
            top_current_cards = series_specific_current_cards.sort_values(by="estimated_value_cents", ascending=False).head(10)
            current_cards_list_ui = [create_card_list_item(card_row) for _, card_row in top_current_cards.iterrows()]
        
        current_cards_section = dbc.Col([
            html.H6("Top Available Cards (Max 10)", className="text-decoration-underline mt-3 mb-2", style={"color": COLORS["text"]}),
            dbc.ListGroup(current_cards_list_ui, flush=True, style={"maxHeight": "300px", "overflowY": "auto"})
        ], md=6, className="mb-3")

        # Sold Cards
        sold_cards_list_ui = [html.P(html.Em("No sales recorded for this series."), style={"color": COLORS["text"]})]
        if not series_specific_sold_events.empty:
            # Already filtered series_specific_sold_events above
            top_sold_cards = series_specific_sold_events.head(10) # Assumes already sorted by sold_at DESC
            sold_cards_list_ui = [create_card_list_item(card_row, type_is_sold=True) for _, card_row in top_sold_cards.iterrows()]

        sold_cards_section = dbc.Col([
            html.H6("Recently Sold Cards (Max 10)", className="text-decoration-underline mt-3 mb-2", style={"color": COLORS["text"]}),
            dbc.ListGroup(sold_cards_list_ui, flush=True, style={"maxHeight": "300px", "overflowY": "auto"})
        ], md=6, className="mb-3")
        
        card_body_children.append(html.Hr(style={"borderColor": COLORS["border_color"]}))
        card_body_children.append(dbc.Row([current_cards_section, sold_cards_section]))

        # --- Accordion Item ---
        cards_accordion_items.append(
            dbc.AccordionItem(
                children=dbc.CardBody(card_body_children, style={"backgroundColor": COLORS["card_background"], "color": COLORS["text"]}),
                title=card_header_content,
                item_id=f"series-item-{series_id}",
                style={"backgroundColor": COLORS["card_background"], "borderColor": COLORS["border_color"]}
            )
        )

    if not cards_accordion_items:
        return html.Div("No series information processed for display.", className="text-warning text-center p-3")
        
    return dbc.Accordion(cards_accordion_items, flush=True, active_item=None, className="mb-3 shadow-sm")

