-- Flipforce/backend/tracker/schema.sql

-- Drop existing tables to ensure a clean slate with the new structure.
-- WARNING: This will delete all existing data in these tables.
DROP TABLE IF EXISTS pack_tier_ev_contribution_snapshots CASCADE;
DROP TABLE IF EXISTS pack_ev_roi_snapshots CASCADE;
DROP TABLE IF EXISTS pack_sales_tracker CASCADE;
DROP TABLE IF EXISTS pack_total_value_snapshots CASCADE;
DROP TABLE IF EXISTS suspected_swapped_cards CASCADE; -- If you added this
DROP TABLE IF EXISTS series_processing_state CASCADE; -- If you added this
DROP TABLE IF EXISTS sold_card_events CASCADE;
DROP TABLE IF EXISTS pack_card_snapshots CASCADE;
DROP TABLE IF EXISTS pack_max_sold CASCADE;
DROP TABLE IF EXISTS pack_snapshots CASCADE;
DROP TABLE IF EXISTS pack_series_metadata CASCADE;

-- Recreate tables with the latest structure
CREATE TABLE IF NOT EXISTS pack_series_metadata (
    series_id UUID PRIMARY KEY,
    name TEXT,
    tier TEXT, 
    cost_cents INTEGER,
    status TEXT,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pack_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    packs_sold INTEGER,
    packs_total INTEGER,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_max_sold (
    series_id UUID PRIMARY KEY,
    max_sold INTEGER,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_card_snapshots (
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    tier TEXT, 
    player_name TEXT,
    overall REAL, 
    insert_name TEXT,
    set_number TEXT,
    set_name TEXT,
    holo TEXT,
    rarity TEXT,
    parallel_number TEXT,
    parallel_total TEXT,
    parallel_name TEXT,
    front_image TEXT,
    back_image TEXT,
    slab_kind TEXT,
    grading_company TEXT,
    estimated_value_cents INTEGER,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- This column is crucial
    PRIMARY KEY (series_id, card_id),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sold_card_events (
    event_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    snapshot_tier TEXT,
    snapshot_estimated_value_cents INTEGER,
    snapshot_player_name TEXT,
    snapshot_set_name TEXT,
    snapshot_insert_name TEXT,
    snapshot_grading_company TEXT,
    snapshot_overall REAL,
    hit_feed_event_id TEXT UNIQUE,
    hit_rate REAL,
    hit_feed_username TEXT,
    hit_feed_avatar_url TEXT,
    hit_feed_number INTEGER,
    hit_feed_tag TEXT,
    hit_feed_player_name TEXT,
    hit_feed_set_name TEXT,
    hit_feed_set_number TEXT,
    hit_feed_parallel_name TEXT,
    hit_feed_parallel_number TEXT,
    hit_feed_parallel_total TEXT,
    hit_feed_front_image_url TEXT,
    hit_feed_back_image_url TEXT,
    hit_feed_grading_company TEXT,
    hit_feed_overall REAL,
    hit_feed_insert_name TEXT,
    hit_feed_arena_club_offer_status TEXT,
    hit_feed_slab_pack_series_name TEXT,
    hit_feed_slab_pack_category_name TEXT,
    sold_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_hit_feed_verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_total_value_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    total_estimated_value_cents BIGINT,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_sales_tracker (
    series_id UUID PRIMARY KEY,
    total_sold INTEGER DEFAULT 0,
    last_checked TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_ev_roi_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    expected_value_cents BIGINT,
    static_pack_cost_cents INTEGER,
    roi REAL,
    num_premium_cards_per_pack INTEGER,
    num_non_premium_cards_per_pack INTEGER,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE,
    UNIQUE (series_id, snapshot_time)
);

CREATE TABLE IF NOT EXISTS pack_tier_ev_contribution_snapshots (
    contribution_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    ev_roi_snapshot_id INTEGER REFERENCES pack_ev_roi_snapshots(snapshot_id) ON DELETE CASCADE,
    tier_api_id UUID,
    tier_name TEXT,
    is_premium BOOLEAN,
    hit_rate REAL,
    num_cards_in_tier INTEGER,
    avg_value_in_tier_cents BIGINT,
    tier_contribution_to_ev_cents BIGINT,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE,
    UNIQUE (ev_roi_snapshot_id, tier_api_id)
);

CREATE TABLE IF NOT EXISTS suspected_swapped_cards (
    swap_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    snapshot_tier TEXT,
    snapshot_player_name TEXT,
    snapshot_estimated_value_cents INTEGER,
    disappeared_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS series_processing_state (
    series_id UUID PRIMARY KEY,
    last_successful_hit_feed_check TIMESTAMP WITH TIME ZONE,
    last_snapshot_cards_processed_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);
