# dashboard/data_fetching.py
import pandas as pd
from config import DB_CONFIG 
from sqlalchemy import create_engine


def get_dashboard_db_engine():
    if not all(
        [
            DB_CONFIG["dbname"],
            DB_CONFIG["user"],
            DB_CONFIG["password"],
            DB_CONFIG["host"],
            str(DB_CONFIG["port"]),
        ]
    ):
        print(
            "[ERROR] Dashboard DB configuration is incomplete. "
            "Check FLIPFORCE_POSTGRES_* environment variables."
        )
        return None
    try:
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
    if not db_engine:
        print("[WARN] fetch_sold_cards_and_pack_metadata: No database engine provided.")
        return pd.DataFrame()
    
    query = """
    SELECT
        sce.series_id, 
        sce.card_id, 
        sce.event_id, 
        sce.snapshot_tier AS card_tier,
        COALESCE(sce.hit_feed_player_name, sce.snapshot_player_name) AS player_name,
        COALESCE(sce.hit_feed_overall, sce.snapshot_overall) AS overall,
        COALESCE(sce.hit_feed_insert_name, sce.snapshot_insert_name) AS insert_name,
        sce.hit_feed_set_number AS set_number,
        COALESCE(sce.hit_feed_set_name, sce.snapshot_set_name) AS set_name,
        sce.hit_feed_parallel_name AS parallel_name,
        sce.hit_feed_parallel_number AS parallel_number,
        sce.hit_feed_parallel_total AS parallel_total,
        sce.hit_feed_front_image_url AS front_image,
        sce.hit_feed_back_image_url AS back_image,
        COALESCE(sce.hit_feed_grading_company, sce.snapshot_grading_company) AS grading_company,
        sce.snapshot_estimated_value_cents AS sold_card_value_cents,
        sce.sold_at,
        psm.name AS pack_name, 
        psm.tier AS pack_category
    FROM sold_card_events sce
    LEFT JOIN pack_series_metadata psm ON sce.series_id = psm.series_id
    ORDER BY sce.series_id, sce.sold_at DESC;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty:
            for col in ["sold_card_value_cents", "overall"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "sold_at" in df.columns:
                df["sold_at"] = pd.to_datetime(df["sold_at"], errors='coerce')
        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch sold cards and pack metadata: {e}")
        print(f"[DEBUG] Failing SQL query in fetch_sold_cards_and_pack_metadata:\n{query}")
        return pd.DataFrame()


def fetch_pack_total_value_data(db_engine):
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
    if not db_engine:
        print("[WARN] fetch_ev_roi_data: No database engine provided.")
        return pd.DataFrame(), pd.DataFrame()

    query_latest_ev_roi = """
    WITH LatestEVROI AS (
        SELECT series_id, expected_value_cents, static_pack_cost_cents, roi,
               expected_value_bb_cents, pack_cost_bb_cents, roi_bb, -- Added new BB columns
               ROW_NUMBER() OVER(PARTITION BY series_id ORDER BY snapshot_time DESC) as rn
        FROM pack_ev_roi_snapshots
    ) SELECT series_id, expected_value_cents, static_pack_cost_cents, roi,
             expected_value_bb_cents, pack_cost_bb_cents, roi_bb -- Added new BB columns
      FROM LatestEVROI WHERE rn = 1;
    """
    latest_ev_roi_df = pd.DataFrame()
    try:
        latest_ev_roi_df = pd.read_sql(query_latest_ev_roi, db_engine)
        if not latest_ev_roi_df.empty:
            cols_to_numeric = [
                "expected_value_cents", "static_pack_cost_cents", "roi",
                "expected_value_bb_cents", "pack_cost_bb_cents", "roi_bb"
            ]
            for col_name in cols_to_numeric:
                 if col_name in latest_ev_roi_df.columns:
                    latest_ev_roi_df[col_name] = pd.to_numeric(latest_ev_roi_df[col_name], errors="coerce")
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest EV/ROI data: {e}")
        print(f"[DEBUG] Failing SQL query in fetch_ev_roi_data (latest):\n{query_latest_ev_roi}")


    # Fetch historical min/max for standard ROI and new ROIBB
    query_min_max_roi = """
    SELECT series_id,
           MIN(roi) as min_historical_roi,
           MAX(roi) as max_historical_roi,
           MIN(roi_bb) as min_historical_roi_bb, -- Added new BB columns
           MAX(roi_bb) as max_historical_roi_bb  -- Added new BB columns
    FROM pack_ev_roi_snapshots GROUP BY series_id;
    """
    min_max_roi_df = pd.DataFrame()
    try:
        min_max_roi_df = pd.read_sql(query_min_max_roi, db_engine)
        if not min_max_roi_df.empty:
            cols_to_numeric_hist = [
                "min_historical_roi", "max_historical_roi",
                "min_historical_roi_bb", "max_historical_roi_bb"
            ]
            for col_name in cols_to_numeric_hist:
                if col_name in min_max_roi_df.columns:
                    min_max_roi_df[col_name] = pd.to_numeric(min_max_roi_df[col_name], errors="coerce")
    except Exception as e:
        print(f"[ERROR] Failed to fetch min/max ROI data: {e}")
        print(f"[DEBUG] Failing SQL query in fetch_ev_roi_data (min/max):\n{query_min_max_roi}")
        
    return latest_ev_roi_df, min_max_roi_df

def fetch_purchase_stats_since_special_hits(db_engine):
    if not db_engine:
        print("[WARN] fetch_purchase_stats_since_special_hits: No database engine provided.")
        return pd.DataFrame()

    query = """
    WITH LastHitTimestamps AS (
        SELECT
            series_id,
            MAX(CASE WHEN lower(snapshot_tier) = 'grail' THEN sold_at ELSE NULL END) as last_grail_ts,
            MAX(CASE WHEN lower(snapshot_tier) = 'chase' THEN sold_at ELSE NULL END) as last_chase_ts
        FROM sold_card_events 
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
            if "count_since_grail" in df.columns:
                 df["count_since_grail"] = pd.to_numeric(df["count_since_grail"], errors='coerce').fillna(0).astype(int)
            if "count_since_chase" in df.columns:
                 df["count_since_chase"] = pd.to_numeric(df["count_since_chase"], errors='coerce').fillna(0).astype(int)

        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch purchase stats since special hits: {e}")
        return pd.DataFrame()

def fetch_current_cards_in_pack(db_engine):
    if not db_engine:
        print("[WARN] fetch_current_cards_in_pack: No database engine provided.")
        return pd.DataFrame()
    
    query = """
    SELECT 
        series_id, 
        card_id, 
        tier, 
        player_name, 
        overall, 
        insert_name, 
        set_number, 
        set_name, 
        holo, 
        rarity, 
        parallel_number, 
        parallel_total, 
        parallel_name, 
        front_image, 
        back_image, 
        slab_kind, 
        grading_company, 
        estimated_value_cents, 
        snapshot_time
    FROM pack_card_snapshots
    ORDER BY series_id, estimated_value_cents DESC;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty:
            for col in ["estimated_value_cents", "overall"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "snapshot_time" in df.columns:
                df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors='coerce')
        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch current cards in pack: {e}")
        print(f"[DEBUG] Failing SQL query in fetch_current_cards_in_pack:\n{query}")
        return pd.DataFrame()

def fetch_high_value_card_counts(db_engine):
    if not db_engine:
        print("[WARN] fetch_high_value_card_counts: No database engine provided.")
        return pd.DataFrame()

    query = """
    SELECT
        psm.series_id,
        psm.cost_cents AS pack_price_cents,
        COUNT(CASE WHEN pcs.estimated_value_cents > psm.cost_cents THEN 1 END) AS cards_over_pack_price_count
    FROM
        pack_series_metadata psm
    LEFT JOIN
        pack_card_snapshots pcs ON psm.series_id = pcs.series_id
    WHERE
        psm.cost_cents IS NOT NULL AND psm.cost_cents > 0 
    GROUP BY
        psm.series_id, psm.cost_cents
    ORDER BY
        psm.series_id;
    """
    try:
        df = pd.read_sql(query, db_engine)
        if not df.empty and "cards_over_pack_price_count" in df.columns:
            df["cards_over_pack_price_count"] = pd.to_numeric(
                df["cards_over_pack_price_count"], errors="coerce"
            ).fillna(0).astype(int)
        if "series_id" in df.columns and "cards_over_pack_price_count" in df.columns:
            return df[["series_id", "cards_over_pack_price_count"]]
        else:
            return pd.DataFrame(columns=["series_id", "cards_over_pack_price_count"])
            
    except Exception as e:
        print(f"[ERROR] Failed to fetch high value card counts: {e}")
        print(f"[DEBUG] Failing SQL query in fetch_high_value_card_counts:\n{query}")
        return pd.DataFrame(columns=["series_id", "cards_over_pack_price_count"])