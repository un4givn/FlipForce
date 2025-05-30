# dashboard/callbacks.py
import traceback  # For detailed error logging

import dash
import numpy as np
import pandas as pd
from config import PACK_CATEGORY_ORDER
from dash import Input, Output, State, callback_context, html
from data_fetching import (
    fetch_ev_roi_data,
    fetch_historical_value_trend_data,
    fetch_pack_total_value_data,
    fetch_sold_cards_and_pack_metadata,
    fetch_purchase_stats_since_special_hits, # New import
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
                    "Please check configuration and logs."
                )
                return html.P(error_message, className="text-danger"), html.Div(
                    error_message, className="text-danger"
                )

            df_sold_cards_and_meta = fetch_sold_cards_and_pack_metadata(db_engine)
            df_latest_total_val, df_hist_min_max_total_val = (
                fetch_pack_total_value_data(db_engine)
            )
            df_hist_val_trend_graph_data = fetch_historical_value_trend_data(db_engine)
            df_latest_ev_roi, df_hist_min_max_roi = fetch_ev_roi_data(db_engine)
            
            # Fetch new purchase stats
            df_purchase_stats = fetch_purchase_stats_since_special_hits(db_engine)


            overall_tier_summary_content = html.P(
                "No card tier data to display for overall summary."
            )
            if (
                not df_sold_cards_and_meta.empty
                and "event_id" in df_sold_cards_and_meta.columns
            ):
                all_sold_cards_for_summary = df_sold_cards_and_meta[
                    df_sold_cards_and_meta["event_id"].notna()
                ]
                if (
                    not all_sold_cards_for_summary.empty
                    and "card_tier" in all_sold_cards_for_summary.columns
                    and not all_sold_cards_for_summary["card_tier"].dropna().empty
                ):
                    overall_tier_counts = all_sold_cards_for_summary[
                        "card_tier"
                    ].value_counts()
                    total_overall_sold_count = overall_tier_counts.sum()
                    overall_tier_list_items = []
                    if total_overall_sold_count > 0:
                        for tier, count in overall_tier_counts.items():
                            percentage = (count / total_overall_sold_count) * 100
                            tier_display = tier if pd.notna(tier) else "Unspecified"
                            overall_tier_list_items.append(
                                html.Li(f"{tier_display}: {count} ({percentage:.1f}%)")
                            )
                    overall_tier_summary_content = html.Ul(
                        overall_tier_list_items
                        if overall_tier_list_items
                        else [html.Li("No tier data in sold cards.")]
                    )
                else:
                    overall_tier_summary_content = html.P(
                        "No card tier data in sold cards for summary."
                    )
            else:
                overall_tier_summary_content = html.P(
                    "No sold card events found for overall summary."
                )

            sql_query = (
                "SELECT series_id, name as pack_name, tier as pack_category "
                "FROM pack_series_metadata"
            )
            df_all_series_meta_from_db = pd.read_sql(sql_query, db_engine)

            if df_all_series_meta_from_db.empty:
                return overall_tier_summary_content, html.Div(
                    "No pack series found in metadata. Tracker might need to run.",
                    className="text-warning",
                )

            df_display_for_cards = df_all_series_meta_from_db.copy()

            if not df_latest_total_val.empty:
                df_display_for_cards = pd.merge(
                    df_display_for_cards,
                    df_latest_total_val,
                    on="series_id",
                    how="left",
                )
            else:
                df_display_for_cards["current_total_available_value_cents"] = np.nan

            if not df_hist_min_max_total_val.empty:
                df_display_for_cards = pd.merge(
                    df_display_for_cards,
                    df_hist_min_max_total_val,
                    on="series_id",
                    how="left",
                )
            else:
                df_display_for_cards["min_historical_total_value_cents"] = np.nan
                df_display_for_cards["max_historical_total_value_cents"] = np.nan

            if not df_latest_ev_roi.empty:
                df_display_for_cards = pd.merge(
                    df_display_for_cards, df_latest_ev_roi, on="series_id", how="left"
                )
            else:
                df_display_for_cards["expected_value_cents"] = np.nan
                df_display_for_cards["static_pack_cost_cents"] = np.nan
                df_display_for_cards["roi"] = np.nan

            if not df_hist_min_max_roi.empty:
                df_display_for_cards = pd.merge(
                    df_display_for_cards,
                    df_hist_min_max_roi,
                    on="series_id",
                    how="left",
                )
            else:
                df_display_for_cards["min_historical_roi"] = np.nan
                df_display_for_cards["max_historical_roi"] = np.nan

            # Merge new purchase stats
            if not df_purchase_stats.empty:
                df_display_for_cards = pd.merge(
                    df_display_for_cards,
                    df_purchase_stats,
                    on="series_id",
                    how="left"
                )
            else: # Ensure columns exist even if fetch fails or returns empty
                df_display_for_cards["last_grail_ts"] = pd.NaT
                df_display_for_cards["count_since_grail"] = np.nan
                df_display_for_cards["last_chase_ts"] = pd.NaT
                df_display_for_cards["count_since_chase"] = np.nan

            # Create display strings for purchase stats
            def determine_display_val(row, count_col_name, ts_col_name, hit_type_str):
                if pd.isna(row[ts_col_name]): # No hit of this type ever recorded
                    return f"No {hit_type_str} Hit Yet"
                else: # A hit was recorded
                    # count_col_name might be NaN if merge failed to find a series, ensure it's int for display
                    count_val = row[count_col_name]
                    return str(int(count_val)) if pd.notna(count_val) else "0"


            df_display_for_cards['purchases_since_grail_str'] = df_display_for_cards.apply(
                determine_display_val, args=('count_since_grail', 'last_grail_ts', 'Grail'), axis=1
            )
            df_display_for_cards['purchases_since_chase_str'] = df_display_for_cards.apply(
                determine_display_val, args=('count_since_chase', 'last_chase_ts', 'Chase'), axis=1
            )


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
            )

            return overall_tier_summary_content, series_cards_ui

        except Exception as e:
            print(f"[ERROR] Callback load_all_dashboard_data failed: {e}")
            traceback.print_exc()
            error_msg = f"Error loading dashboard: {str(e)}"
            return html.P(error_msg, className="text-danger"), html.Div(
                error_msg, className="text-danger"
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

    @app.callback(
        Output({"type": "series-collapse", "index": dash.ALL}, "is_open"),
        Input({"type": "series-toggle", "index": dash.ALL}, "n_clicks"),
        State({"type": "series-collapse", "index": dash.ALL}, "is_open"),
        State({"type": "series-toggle", "index": dash.ALL}, "id"),
        prevent_initial_call=True,
    )
    def toggle_individual_series_collapse(
        n_clicks_list, current_is_open_list, button_ids
    ):
        ctx = callback_context
        if not ctx.triggered_id or not n_clicks_list:
            return current_is_open_list

        triggered_button_id_str = ctx.triggered_id.get("index")
        if triggered_button_id_str is None:
            return current_is_open_list

        new_is_open_list = list(current_is_open_list)
        for i, button_id_dict in enumerate(button_ids):
            if (
                str(button_id_dict.get("index")) == triggered_button_id_str
                and n_clicks_list[i] is not None
            ):
                new_is_open_list[i] = not current_is_open_list[i]
                break
        return new_is_open_list