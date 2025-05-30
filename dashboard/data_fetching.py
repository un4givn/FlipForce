# dashboard/data_fetching.py
import pandas as pd
from config import DB_CONFIG
from sqlalchemy import create_engine


def get_dashboard_db_engine():
    """Establishes and returns a SQLAlchemy database engine for the dashboard."""
    if not all(
        [
            DB_CONFIG["dbname"],
            DB_CONFIG["user"],
            DB_CONFIG["password"],
            DB_CONFIG["host"],
        ]
    ):
        print(
            "[ERROR] Dashboard DB configuration is incomplete. "
            "Check environment variables."
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
    """Fetches sold card events joined with pack series metadata."""
    if not db_engine:
        return pd.DataFrame()
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
    df = pd.read_sql(query, db_engine)
    if not df.empty:
        for col in ["sold_card_value_cents", "overall"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "sold_at" in df.columns:
            df["sold_at"] = pd.to_datetime(df["sold_at"])
    return df


def fetch_pack_total_value_data(db_engine):
    """Fetches current total available value (sum of cards) and its
    historical min/max."""
    if not db_engine:
        return pd.DataFrame(), pd.DataFrame()

    query_latest_total_value = """
    WITH LatestPackValue AS (
        SELECT series_id,
               total_estimated_value_cents AS current_total_available_value_cents,
               ROW_NUMBER() OVER(PARTITION BY series_id
                                 ORDER BY snapshot_time DESC) as rn
        FROM pack_total_value_snapshots
    ) SELECT series_id, current_total_available_value_cents
      FROM LatestPackValue WHERE rn = 1;
    """
    latest_df = pd.read_sql(query_latest_total_value, db_engine)
    if (
        not latest_df.empty
        and "current_total_available_value_cents" in latest_df.columns
    ):
        latest_df["current_total_available_value_cents"] = pd.to_numeric(
            latest_df["current_total_available_value_cents"], errors="coerce"
        )

    query_min_max_total_value = """
    SELECT series_id,
           MIN(total_estimated_value_cents) as min_historical_total_value_cents,
           MAX(total_estimated_value_cents) as max_historical_total_value_cents
    FROM pack_total_value_snapshots GROUP BY series_id;
    """
    min_max_df = pd.read_sql(query_min_max_total_value, db_engine)
    return latest_df, min_max_df


def fetch_historical_value_trend_data(db_engine):
    """Fetches all historical total available values (sum of cards) for trend graphs."""
    if not db_engine:
        return pd.DataFrame()
    query = """
    SELECT series_id, total_estimated_value_cents, snapshot_time
    FROM pack_total_value_snapshots
    ORDER BY series_id, snapshot_time ASC;
    """
    df = pd.read_sql(query, db_engine)
    if not df.empty:
        df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])
        if "total_estimated_value_cents" in df.columns:
            df["total_estimated_value_cents"] = pd.to_numeric(
                df["total_estimated_value_cents"], errors="coerce"
            )
    return df


def fetch_ev_roi_data(db_engine):
    """Fetches latest EV/ROI and historical min/max ROI for the dashboard."""
    if not db_engine:
        return pd.DataFrame(), pd.DataFrame()

    query_latest_ev_roi = """
    WITH LatestEVROI AS (
        SELECT series_id, expected_value_cents, static_pack_cost_cents, roi,
               ROW_NUMBER() OVER(PARTITION BY series_id
                                 ORDER BY snapshot_time DESC) as rn
        FROM pack_ev_roi_snapshots
    ) SELECT series_id, expected_value_cents, static_pack_cost_cents, roi
      FROM LatestEVROI WHERE rn = 1;
    """
    latest_ev_roi_df = pd.read_sql(query_latest_ev_roi, db_engine)

    query_min_max_roi = """
    SELECT series_id,
           MIN(roi) as min_historical_roi,
           MAX(roi) as max_historical_roi
    FROM pack_ev_roi_snapshots GROUP BY series_id;
    """
    min_max_roi_df = pd.read_sql(query_min_max_roi, db_engine)
    return latest_ev_roi_df, min_max_roi_df

def fetch_purchase_stats_since_special_hits(db_engine):
    """
    Fetches statistics on card purchases since the last 'Grail' or 'Chase' tier card was sold for each series.
    Returns a DataFrame with series_id, last_grail_ts, last_chase_ts, count_since_grail, count_since_chase.
    Timestamps will be NaT if no such hit has occurred.
    Counts will be the number of cards sold after the respective hit; 0 if a hit occurred but no sales after.
    """
    if not db_engine:
        return pd.DataFrame()

    query = """
    WITH LastHitTimestamps AS (
        SELECT
            series_id,
            MAX(CASE WHEN lower(tier) = 'grail' THEN sold_at ELSE NULL END) as last_grail_ts,
            MAX(CASE WHEN lower(tier) = 'chase' THEN sold_at ELSE NULL END) as last_chase_ts
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
    df = pd.read_sql(query, db_engine)
    if not df.empty:
        if "last_grail_ts" in df.columns:
            df["last_grail_ts"] = pd.to_datetime(df["last_grail_ts"], errors='coerce')
        if "last_chase_ts" in df.columns:
            df["last_chase_ts"] = pd.to_datetime(df["last_chase_ts"], errors='coerce')
    return df