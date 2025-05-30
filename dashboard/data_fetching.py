# dashboard/data_fetching.py
import pandas as pd
from config import DB_CONFIG # Assuming DB_CONFIG is correctly defined in config.py
from sqlalchemy import create_engine


def get_dashboard_db_engine():
    """Establishes and returns a SQLAlchemy database engine for the dashboard."""
    if not all(
        [
            DB_CONFIG["dbname"],
            DB_CONFIG["user"],
            DB_CONFIG["password"],
            DB_CONFIG["host"],
            str(DB_CONFIG["port"]), # Ensure port is also checked
        ]
    ):
        print(
            "[ERROR] Dashboard DB configuration is incomplete. "
            "Check FLIPFORCE_POSTGRES_* environment variables."
        )
        return None
    try:
        # Construct the database URI
        db_uri = (
            f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        engine = create_engine(db_uri)
        return engine
    except Exception as e:
        print(f"[ERROR] Dashboard failed to create SQLAlchemy engine: {e}")
        return None


def fetch_sold_cards_and_pack_metadata(db_engine):
    """Fetches sold card events joined with pack series metadata."""
    if not db_engine:
        print("[WARN] fetch_sold_cards_and_pack_metadata: No database engine provided.")
        return pd.DataFrame()
    
    # Corrected query:
    # - Uses sce.snapshot_tier AS card_tier
    # - Uses COALESCE for fields that could come from snapshot or hit_feed, prioritizing hit_feed where sensible for display.
    # - Assumes you want to display the card's state as it was recorded sold.
    query = """
    SELECT
        sce.series_id, 
        sce.card_id, 
        sce.event_id, 
        sce.snapshot_tier AS card_tier,                                         -- Tier from your snapshot
        COALESCE(sce.hit_feed_player_name, sce.snapshot_player_name) AS player_name, -- Prefer hit_feed if available
        COALESCE(sce.hit_feed_overall, sce.snapshot_overall) AS overall,             -- Prefer hit_feed if available
        COALESCE(sce.hit_feed_insert_name, sce.snapshot_insert_name) AS insert_name, -- Prefer hit_feed if available
        sce.hit_feed_set_number AS set_number,                                   -- From hit_feed
        COALESCE(sce.hit_feed_set_name, sce.snapshot_set_name) AS set_name,           -- Prefer hit_feed if available
        sce.hit_feed_parallel_name AS parallel_name,                             -- From hit_feed
        sce.hit_feed_parallel_number AS parallel_number,                         -- From hit_feed
        sce.hit_feed_parallel_total AS parallel_total,                           -- From hit_feed
        sce.hit_feed_front_image_url AS front_image,                             -- From hit_feed
        sce.hit_feed_back_image_url AS back_image,                               -- From hit_feed
        COALESCE(sce.hit_feed_grading_company, sce.snapshot_grading_company) AS grading_company, -- Prefer hit_feed
        sce.snapshot_estimated_value_cents AS sold_card_value_cents,             -- Value from your snapshot at time of sale detection
        sce.sold_at,                                                             -- Actual sale time from hit_feed or tracker record time
        psm.name AS pack_name, 
        psm.tier AS pack_category  -- This is the tier of the pack itself
    FROM sold_card_events sce
    LEFT JOIN pack_series_metadata psm ON sce.series_id = psm.series_id
    ORDER BY sce.series_id, sce.sold_at DESC;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty:
            # Ensure numeric columns are correctly typed
            for col in ["sold_card_value_cents", "overall"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "sold_at" in df.columns:
                df["sold_at"] = pd.to_datetime(df["sold_at"], errors='coerce')
        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch sold cards and pack metadata: {e}")
        # In case of an error, print the SQL query for debugging
        print(f"[DEBUG] Failing SQL query in fetch_sold_cards_and_pack_metadata:\n{query}")
        return pd.DataFrame()


def fetch_pack_total_value_data(db_engine):
    """Fetches current total available value (sum of cards) and its historical min/max."""
    if not db_engine:
        print("[WARN] fetch_pack_total_value_data: No database engine provided.")
        return pd.DataFrame(), pd.DataFrame()

    query_latest_total_value = """
    WITH LatestPackValue AS (
        SELECT series_id,
               total_estimated_value_cents AS current_total_available_value_cents,
               ROW_NUMBER() OVER(PARTITION BY series_id ORDER BY snapshot_time DESC) as rn
        FROM pack_total_value_snapshots
    ) SELECT series_id, current_total_available_value_cents
      FROM LatestPackValue WHERE rn = 1;
    """
    latest_df = pd.DataFrame()
    try:
        latest_df = pd.read_sql(query_latest_total_value, db_engine)
        if not latest_df.empty and "current_total_available_value_cents" in latest_df.columns:
            latest_df["current_total_available_value_cents"] = pd.to_numeric(
                latest_df["current_total_available_value_cents"], errors="coerce"
            )
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest pack total value: {e}")

    query_min_max_total_value = """
    SELECT series_id,
           MIN(total_estimated_value_cents) as min_historical_total_value_cents,
           MAX(total_estimated_value_cents) as max_historical_total_value_cents
    FROM pack_total_value_snapshots GROUP BY series_id;
    """
    min_max_df = pd.DataFrame()
    try:
        min_max_df = pd.read_sql(query_min_max_total_value, db_engine)
        if not min_max_df.empty:
            for col_name in ["min_historical_total_value_cents", "max_historical_total_value_cents"]:
                if col_name in min_max_df.columns:
                    min_max_df[col_name] = pd.to_numeric(min_max_df[col_name], errors="coerce")
    except Exception as e:
        print(f"[ERROR] Failed to fetch min/max pack total value: {e}")
        
    return latest_df, min_max_df


def fetch_historical_value_trend_data(db_engine):
    """Fetches all historical total available values (sum of cards) for trend graphs."""
    if not db_engine:
        print("[WARN] fetch_historical_value_trend_data: No database engine provided.")
        return pd.DataFrame()
    query = """
    SELECT series_id, total_estimated_value_cents, snapshot_time
    FROM pack_total_value_snapshots
    ORDER BY series_id, snapshot_time ASC;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty:
            df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors='coerce')
            if "total_estimated_value_cents" in df.columns:
                df["total_estimated_value_cents"] = pd.to_numeric(
                    df["total_estimated_value_cents"], errors="coerce"
                )
        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch historical value trend data: {e}")
        return pd.DataFrame()


def fetch_ev_roi_data(db_engine):
    """Fetches latest EV/ROI and historical min/max ROI for the dashboard."""
    if not db_engine:
        print("[WARN] fetch_ev_roi_data: No database engine provided.")
        return pd.DataFrame(), pd.DataFrame()

    query_latest_ev_roi = """
    WITH LatestEVROI AS (
        SELECT series_id, expected_value_cents, static_pack_cost_cents, roi,
               ROW_NUMBER() OVER(PARTITION BY series_id ORDER BY snapshot_time DESC) as rn
        FROM pack_ev_roi_snapshots
    ) SELECT series_id, expected_value_cents, static_pack_cost_cents, roi
      FROM LatestEVROI WHERE rn = 1;
    """
    latest_ev_roi_df = pd.DataFrame()
    try:
        latest_ev_roi_df = pd.read_sql(query_latest_ev_roi, db_engine)
        if not latest_ev_roi_df.empty:
            for col_name in ["expected_value_cents", "static_pack_cost_cents", "roi"]:
                 if col_name in latest_ev_roi_df.columns:
                    latest_ev_roi_df[col_name] = pd.to_numeric(latest_ev_roi_df[col_name], errors="coerce")
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest EV/ROI data: {e}")

    query_min_max_roi = """
    SELECT series_id,
           MIN(roi) as min_historical_roi,
           MAX(roi) as max_historical_roi
    FROM pack_ev_roi_snapshots GROUP BY series_id;
    """
    min_max_roi_df = pd.DataFrame()
    try:
        min_max_roi_df = pd.read_sql(query_min_max_roi, db_engine)
        if not min_max_roi_df.empty:
            for col_name in ["min_historical_roi", "max_historical_roi"]:
                if col_name in min_max_roi_df.columns:
                    min_max_roi_df[col_name] = pd.to_numeric(min_max_roi_df[col_name], errors="coerce")
    except Exception as e:
        print(f"[ERROR] Failed to fetch min/max ROI data: {e}")
        
    return latest_ev_roi_df, min_max_roi_df

def fetch_purchase_stats_since_special_hits(db_engine):
    """
    Fetches statistics on card purchases since the last 'Grail' or 'Chase' tier card was sold for each series.
    It uses snapshot_tier for identifying Grails/Chases.
    """
    if not db_engine:
        print("[WARN] fetch_purchase_stats_since_special_hits: No database engine provided.")
        return pd.DataFrame()

    query = """
    WITH LastHitTimestamps AS (
        SELECT
            series_id,
            MAX(CASE WHEN lower(snapshot_tier) = 'grail' THEN sold_at ELSE NULL END) as last_grail_ts,
            MAX(CASE WHEN lower(snapshot_tier) = 'chase' THEN sold_at ELSE NULL END) as last_chase_ts
        FROM sold_card_events -- Using snapshot_tier here
        GROUP BY series_id
    )
    SELECT
        psm.series_id,
        lhts.last_grail_ts,
        lhts.last_chase_ts,
        (SELECT COUNT(sce.event_id)
         FROM sold_card_events sce
         WHERE sce.series_id = psm.series_id AND lhts.last_grail_ts IS NOT NULL AND sce.sold_at > lhts.last_grail_ts
        ) as count_since_grail,
        (SELECT COUNT(sce.event_id)
         FROM sold_card_events sce
         WHERE sce.series_id = psm.series_id AND lhts.last_chase_ts IS NOT NULL AND sce.sold_at > lhts.last_chase_ts
        ) as count_since_chase
    FROM pack_series_metadata psm
    LEFT JOIN LastHitTimestamps lhts ON psm.series_id = lhts.series_id;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty:
            if "last_grail_ts" in df.columns:
                df["last_grail_ts"] = pd.to_datetime(df["last_grail_ts"], errors='coerce')
            if "last_chase_ts" in df.columns:
                df["last_chase_ts"] = pd.to_datetime(df["last_chase_ts"], errors='coerce')
            # Ensure count columns are numeric integers
            if "count_since_grail" in df.columns:
                 df["count_since_grail"] = pd.to_numeric(df["count_since_grail"], errors='coerce').fillna(0).astype(int)
            if "count_since_chase" in df.columns:
                 df["count_since_chase"] = pd.to_numeric(df["count_since_chase"], errors='coerce').fillna(0).astype(int)

        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch purchase stats since special hits: {e}")
        return pd.DataFrame()
