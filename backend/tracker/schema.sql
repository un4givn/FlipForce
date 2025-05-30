-- Flipforce/backend/tracker/schema.sql

CREATE TABLE IF NOT EXISTS pack_series_metadata (
    series_id UUID PRIMARY KEY,
    name TEXT,
    tier TEXT, -- This tier is for the series/pack itself (e.g., Diamond, Emerald)
    cost_cents INTEGER, -- Cost from API, might differ from static cost for ROI
    status TEXT,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pack_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    packs_sold INTEGER,
    packs_total INTEGER,
    snapshot_time TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_max_sold (
    series_id UUID PRIMARY KEY,
    max_sold INTEGER,
    last_updated TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_card_snapshots (
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    tier TEXT, -- Card's own tier from within the pack (e.g. Grail, Chase, Lineup)
    player_name TEXT,
    overall INTEGER,
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
    PRIMARY KEY (series_id, card_id),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sold_card_events (
    event_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    tier TEXT, -- Card's own tier (e.g. Grail, Chase, Lineup)
    player_name TEXT,
    overall INTEGER,
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
    sold_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_total_value_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    total_estimated_value_cents BIGINT, -- Sum of all available cards' values in the pack
    snapshot_time TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pack_sales_tracker (
    series_id UUID PRIMARY KEY,
    total_sold INTEGER DEFAULT 0,
    last_checked TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE
);

-- Stores calculated Expected Value and ROI based on hit rates
CREATE TABLE IF NOT EXISTS pack_ev_roi_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    expected_value_cents BIGINT, -- Calculated EV from opening one pack
    static_pack_cost_cents INTEGER, -- The static cost used for this ROI calc
    roi REAL, -- Return on Investment (e.g., 0.5 for 50% ROI)
    num_premium_cards_per_pack INTEGER,
    num_non_premium_cards_per_pack INTEGER,
    snapshot_time TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE,
    UNIQUE (series_id, snapshot_time) -- Ensure one EV/ROI snapshot per series at a given time
);

-- Stores details of each tier's contribution to EV at snapshot time
CREATE TABLE IF NOT EXISTS pack_tier_ev_contribution_snapshots (
    contribution_id SERIAL PRIMARY KEY,
    series_id UUID NOT NULL,
    ev_roi_snapshot_id INTEGER REFERENCES pack_ev_roi_snapshots(snapshot_id) ON DELETE CASCADE,
    tier_api_id UUID, -- The ID of the tier from the API (e.g., slabPackTiers[i].id)
    tier_name TEXT,
    is_premium BOOLEAN,
    hit_rate REAL,
    num_cards_in_tier INTEGER,
    avg_value_in_tier_cents BIGINT,
    tier_contribution_to_ev_cents BIGINT, -- avg_value_in_tier_cents * hit_rate
    snapshot_time TIMESTAMP DEFAULT NOW(), -- Useful for direct queries
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) ON DELETE CASCADE,
    UNIQUE (ev_roi_snapshot_id, tier_api_id) -- Ensure one entry per tier per EV snapshot
);