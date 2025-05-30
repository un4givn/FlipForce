-- Add these table definitions to your Flipforce/backend/tracker/schema.sql file

CREATE TABLE IF NOT EXISTS pack_series_metadata (
    series_id UUID PRIMARY KEY,
    name TEXT,
    tier TEXT, -- This tier is for the series/pack itself
    cost_cents INTEGER,
    status TEXT,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pack_snapshots ( -- This table is used in store_snapshot_and_update_max
    snapshot_id SERIAL PRIMARY KEY, -- Added a primary key for this table
    series_id UUID NOT NULL,
    packs_sold INTEGER,
    packs_total INTEGER,
    snapshot_time TIMESTAMP DEFAULT NOW(), -- Timestamp for when the snapshot was taken
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) -- Optional: Foreign key
);

CREATE TABLE IF NOT EXISTS pack_max_sold (
    series_id UUID PRIMARY KEY,
    max_sold INTEGER,
    last_updated TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id) -- Optional: Foreign key
);

-- Ensure pack_card_snapshots is defined as it's used extensively
CREATE TABLE IF NOT EXISTS pack_card_snapshots (
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    tier TEXT, -- <<< ADDED: To store the tier name for the card
    player_name TEXT,
    overall INTEGER,
    insert_name TEXT, -- Matches the INSERT statement in tracker.py
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
    PRIMARY KEY (series_id, card_id)
    -- Optional: FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id)
);

-- Ensure sold_card_events is defined
CREATE TABLE IF NOT EXISTS sold_card_events (
    event_id SERIAL PRIMARY KEY, -- Added a primary key
    series_id UUID NOT NULL,
    card_id UUID NOT NULL,
    tier TEXT, -- <<< ADDED/CONFIRMED: To store the tier name for the card event
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
    sold_at TIMESTAMP DEFAULT NOW()
    -- Optional: FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id)
);

-- Ensure pack_sales_tracker is defined
CREATE TABLE IF NOT EXISTS pack_sales_tracker (
    series_id UUID PRIMARY KEY,
    total_sold INTEGER DEFAULT 0,
    last_checked TIMESTAMP
    -- Optional: FOREIGN KEY (series_id) REFERENCES pack_series_metadata(series_id)
);