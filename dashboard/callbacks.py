# dashboard/callbacks.py
import traceback

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback_context, html

from config import PACK_CATEGORY_ORDER, COLORS # Import COLORS
from data_fetching import (
    fetch_current_cards_in_pack,
    fetch_ev_roi_data,
    fetch_high_value_card_counts,
    fetch_historical_value_trend_data,
    fetch_pack_total_value_data,
    fetch_purchase_stats_since_special_hits,
    fetch_sold_cards_and_pack_metadata,
    get_dashboard_db_engine,
)
from ui_components import make_series_cards


def register_callbacks(app):
    @app.callback(
        Output("tier-body-content", "children"),
        Output("series-card-container", "children"),
        Input("data-refresh-interval", "n_intervals"),
    )
    def load_all_dashboard_data(n_intervals):
        db_engine = None
        try:
            db_engine = get_dashboard_db_engine()
            if not db_engine:
                error_message = (
                    "Failed to create database engine. "
                    "Check configuration and logs."
                )
                return html.P(error_message, className="text-danger"), dbc.Alert(
                    error_message, color="danger", className="m-3"
                )

            # Fetch all data
            df_sold_cards_and_meta = fetch_sold_cards_and_pack_metadata(db_engine)
            df_latest_total_val, df_hist_min_max_total_val = fetch_pack_total_value_data(db_engine)
            df_hist_val_trend_graph_data = fetch_historical_value_trend_data(db_engine)
            df_latest_ev_roi, df_hist_min_max_roi = fetch_ev_roi_data(db_engine)
            df_purchase_stats = fetch_purchase_stats_since_special_hits(db_engine)
            df_current_cards = fetch_current_cards_in_pack(db_engine)
            df_high_value_counts = fetch_high_value_card_counts(db_engine)

            # Process Overall Tier Summary
            overall_tier_summary_content = html.P("No card tier data for overall summary.", style={"color": COLORS["text"]})
            if not df_sold_cards_and_meta.empty and "event_id" in df_sold_cards_and_meta.columns:
                all_sold_for_summary = df_sold_cards_and_meta[df_sold_cards_and_meta["event_id"].notna()]
                if not all_sold_for_summary.empty and "card_tier" in all_sold_for_summary.columns and not all_sold_for_summary["card_tier"].dropna().empty:
                    overall_tier_counts = all_sold_for_summary["card_tier"].value_counts()
                    total_overall_sold = overall_tier_counts.sum()
                    if total_overall_sold > 0:
                        items = [
                            html.Li(f"{tier if pd.notna(tier) else 'Unspecified'}: {count} ({(count / total_overall_sold) * 100:.1f}%)", style={"color": COLORS["text"]})
                            for tier, count in overall_tier_counts.items()
                        ]
                        overall_tier_summary_content = html.Ul(items, className="list-unstyled")
                else:
                    overall_tier_summary_content = html.P("No card tier data in sold cards for summary.", style={"color": COLORS["text"]})
            else:
                overall_tier_summary_content = html.P("No sold card events for overall summary.", style={"color": COLORS["text"]})


            # Prepare base series data for cards
            sql_query = "SELECT series_id, name as pack_name, tier as pack_category FROM pack_series_metadata"
            df_all_series_meta_from_db = pd.read_sql(sql_query, db_engine)

            if df_all_series_meta_from_db.empty:
                return overall_tier_summary_content, dbc.Alert(
                    "No pack series found in metadata. Tracker might need to run.",
                    color="warning", className="m-3"
                )

            df_display_for_cards = df_all_series_meta_from_db.copy()

            # Merge all fetched dataframes
            merge_dfs = {
                "latest_total_val": df_latest_total_val,
                "hist_min_max_total_val": df_hist_min_max_total_val,
                "latest_ev_roi": df_latest_ev_roi,
                "hist_min_max_roi": df_hist_min_max_roi,
                "purchase_stats": df_purchase_stats,
                "high_value_counts": df_high_value_counts,
            }
            
            default_cols = {
                "latest_total_val": ["current_total_available_value_cents"],
                "hist_min_max_total_val": ["min_historical_total_value_cents", "max_historical_total_value_cents"],
                "latest_ev_roi": ["expected_value_cents", "static_pack_cost_cents", "roi", "expected_value_bb_cents", "pack_cost_bb_cents", "roi_bb"],
                "hist_min_max_roi": ["min_historical_roi", "max_historical_roi", "min_historical_roi_bb", "max_historical_roi_bb"],
                "purchase_stats": ["last_grail_ts", "count_since_grail", "last_chase_ts", "count_since_chase"],
                "high_value_counts": ["cards_over_pack_price_count"],
            }

            for key, df_to_merge in merge_dfs.items():
                if not df_to_merge.empty:
                    df_display_for_cards = pd.merge(df_display_for_cards, df_to_merge, on="series_id", how="left")
                else:
                    for col in default_cols.get(key, []):
                        df_display_for_cards[col] = np.nan if "roi" in col or "value" in col or "cost" in col else (pd.NaT if "ts" in col else 0)
            
            # Special handling for count columns to be integer and fillna(0)
            count_like_cols = ["cards_over_pack_price_count", "count_since_grail", "count_since_chase"]
            for col in count_like_cols:
                if col in df_display_for_cards.columns:
                    df_display_for_cards[col] = df_display_for_cards[col].fillna(0).astype(int)
                else: # Ensure column exists if merge failed to create it
                    df_display_for_cards[col] = 0


            # Purchases since grail/chase strings
            def determine_display_val(row, count_col, ts_col, hit_type):
                if pd.isna(row[ts_col]):
                    return f"No {hit_type} Hit Yet"
                count_val = row[count_col]
                return str(int(count_val)) if pd.notna(count_val) else "0"

            if "count_since_grail" in df_display_for_cards.columns and "last_grail_ts" in df_display_for_cards.columns:
                df_display_for_cards['purchases_since_grail_str'] = df_display_for_cards.apply(
                    determine_display_val, args=('count_since_grail', 'last_grail_ts', 'Grail'), axis=1
                )
            else:
                df_display_for_cards['purchases_since_grail_str'] = "N/A"

            if "count_since_chase" in df_display_for_cards.columns and "last_chase_ts" in df_display_for_cards.columns:
                df_display_for_cards['purchases_since_chase_str'] = df_display_for_cards.apply(
                    determine_display_val, args=('count_since_chase', 'last_chase_ts', 'Chase'), axis=1
                )
            else:
                df_display_for_cards['purchases_since_chase_str'] = "N/A"


            # Sort data
            if "pack_category" in df_display_for_cards.columns:
                df_display_for_cards["pack_category_ordered"] = pd.Categorical(
                    df_display_for_cards["pack_category"].fillna("Unknown Category"),
                    categories=PACK_CATEGORY_ORDER,
                    ordered=True,
                )
                df_display_for_cards.sort_values(
                    by=["pack_category_ordered", "pack_name", "series_id"],
                    ascending=[True, True, True],
                    inplace=True,
                    na_position="last",
                )

            series_cards_ui = make_series_cards(
                df_display_for_cards,
                df_hist_val_trend_graph_data,
                df_sold_cards_and_meta,
                df_current_cards
            )

            return overall_tier_summary_content, series_cards_ui

        except Exception as e:
            print(f"[ERROR] Callback load_all_dashboard_data failed: {e}")
            traceback.print_exc()
            error_msg_detail = f"Error loading dashboard: {str(e)}. Check console for details."
            return dbc.Alert(error_msg_detail, color="danger", className="m-3"), dbc.Alert(
                error_msg_detail, color="danger", className="m-3"
            )
        finally:
            if db_engine:
                db_engine.dispose()

    @app.callback(
        Output("tier-collapse", "is_open"),
        Input("tier-toggle", "n_clicks"),
        State("tier-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_tier_summary_collapse(n_clicks, is_open):
        return not is_open if n_clicks else is_open

    # Note: The accordion in ui_components.py handles its own open/close state.
    # If you used individual dbc.Collapse components per series card, you'd need a callback similar to the one
    # you had before for `{"type": "series-collapse", "index": dash.ALL}`.
    # Since we switched to dbc.Accordion, this specific callback might no longer be needed
    # unless you have other collapsible components that are not part of the main accordion.
    # For now, I'll comment it out as dbc.Accordion manages its items.

    # @app.callback(
    #     Output({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    #     Input({"type": "series-toggle", "index": dash.ALL}, "n_clicks"),
    #     State({"type": "series-collapse", "index": dash.ALL}, "is_open"),
    #     State({"type": "series-toggle", "index": dash.ALL}, "id"),
    #     prevent_initial_call=True,
    # )
    # def toggle_individual_series_collapse(
    #     n_clicks_list, current_is_open_list, button_ids
    # ):
    #     ctx = callback_context
    #     if not ctx.triggered_id or not n_clicks_list:
    #         return current_is_open_list

    #     triggered_button_id_str = ctx.triggered_id.get("index")
    #     if triggered_button_id_str is None:
    #         return current_is_open_list

    #     new_is_open_list = list(current_is_open_list) # Make a mutable copy
    #     for i, button_id_dict in enumerate(button_ids):
    #         if (
    #             str(button_id_dict.get("index")) == triggered_button_id_str
    #             and n_clicks_list[i] is not None # Ensure the click corresponds to this button
    #         ):
    #             new_is_open_list[i] = not current_is_open_list[i]
    #             break # Found the button, no need to continue
    #     return new_is_open_list
