import os
import time
from datetime import datetime, timezone
import psycopg2
import requests
from dateutil import parser # For parsing ISO 8601 dates
from config import get_db_connection # Assuming this is correctly set up

print("[TrackerDiag] tracker.py execution started - TOP OF FILE")
print("[Tracker] ✅ tracker.py has started.")

# Define the packs you want to track by their category and series name
TARGET_PACKS_TO_TRACK = [
    {"category_name": "Diamond", "series_name": "Multi-Sport"},
    {"category_name": "Diamond", "series_name": "Pokemon"},
    {"category_name": "Emerald", "series_name": "Baseball"},
    {"category_name": "Emerald", "series_name": "Basketball"},
    {"category_name": "Emerald", "series_name": "Football"},
    {"category_name": "Emerald", "series_name": "Pokemon"},
    {"category_name": "Ruby", "series_name": "Baseball"},
    {"category_name": "Ruby", "series_name": "Basketball"},
    {"category_name": "Ruby", "series_name": "Football"},
    {"category_name": "Ruby", "series_name": "Pokemon"},
    {"category_name": "Gold", "series_name": "Baseball"},
    {"category_name": "Gold", "series_name": "Basketball"},
    {"category_name": "Gold", "series_name": "Football"},
    {"category_name": "Gold", "series_name": "Pokemon"},
    {"category_name": "Silver", "series_name": "Baseball"},
    {"category_name": "Silver", "series_name": "Basketball"},
    {"category_name": "Silver", "series_name": "Football"},
    {"category_name": "Silver", "series_name": "Pokemon"},
    {"category_name": "Misc.", "series_name": "Multi-Sport"},
    {"category_name": "Misc.", "series_name": "Pokemon"},
]

SLAB_PACK_CATEGORIES_URL = "https://api.arenaclub.com/v2/slab-pack-categories"
ARENA_CLUB_API_BASE_URL = "https://api.arenaclub.com/v2/slab-pack-series/"
HIT_FEED_API_URL = "https://api.arenaclub.com/v2/card-hit-feed"

STATIC_PACK_COSTS_CENTS = {
    "Diamond": 100000, "Emerald": 50000, "Ruby": 25000,
    "Gold": 10000, "Silver": 5000, "Misc.": 2500, "Misc": 2500,
}
TIERS_TO_VERIFY_ON_HIT_FEED = ["Grail", "Chase"] # Tiers requiring hit feed verification

# --- Helper Functions ---
def get_static_pack_cost(pack_category_name):
    """Gets the static cost for a given pack category name."""
    if not pack_category_name: return None
    cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name)
    if cost is None: # Try matching common variations if direct match fails
        if pack_category_name.endswith("."):
            cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name[:-1])
        else:
            cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name + ".")
    return cost

def fetch_api_data(url, params=None, headers=None, timeout=30):
    """Generic function to fetch data from an API."""
    # Standard headers that seem to work for ArenaClub APIs
    effective_headers = {
        'accept': 'application/json, text/plain, */*',
        'origin': 'https://arenaclub.com',
        'referer': 'https://arenaclub.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    }
    if headers: # Allow overriding or adding headers if needed
        effective_headers.update(headers)
    
    current_time_str = datetime.now(timezone.utc).isoformat()
    try:
        print(f"[{current_time_str}] Fetching API: {url} with params: {params}")
        response = requests.get(url, headers=effective_headers, params=params, timeout=timeout)
        response.raise_for_status() # Raises HTTPError for bad responses (4XX/5XX)
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[{current_time_str}] HTTP error for {url}: {e}. Response: {e.response.text if e.response else 'No response'}")
    except requests.exceptions.RequestException as e: # Other request errors (network, timeout)
        print(f"[{current_time_str}] Request error for {url}: {e}")
    except ValueError as e: # JSON decoding error
        print(f"[{current_time_str}] JSON decoding error for {url}: {e}")
    return None # Return None on any failure

def fetch_all_pack_data_from_categories_endpoint():
    """Fetches the complete list of pack categories and their associated series."""
    return fetch_api_data(SLAB_PACK_CATEGORIES_URL)

def fetch_slab_pack(series_id):
    """Fetches detailed data for a specific slab pack series using its series ID."""
    api_url = f"{ARENA_CLUB_API_BASE_URL}{series_id}"
    return fetch_api_data(api_url)

def fetch_hit_feed_data_api(limit=50, offset=0):
    """Fetches the hit feed data from the ArenaClub API."""
    params = {'limit': limit, 'offset': offset, 'category': 'all'}
    data = fetch_api_data(HIT_FEED_API_URL, params=params)
    if data and "items" in data:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Successfully fetched {len(data['items'])} items from hit feed API.")
        return data["items"]
    print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: No items found in hit feed API response or response error.")
    return [] # Return empty list on failure or no items to ensure type consistency

def run_schema_sql(conn):
    """Loads and executes the schema.sql file."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r") as f:
            sql_commands = f.read()
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        conn.commit()
        print(f"[{datetime.now(timezone.utc).isoformat()}] Schema loaded/verified successfully.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] FATAL: Failed to run schema.sql: {e}")
        if conn:
            conn.rollback()
        raise # Re-raise the exception to halt execution if schema fails

def store_metadata_and_sales_snapshot(conn, pack_detail_data):
    """Stores pack metadata, current sales snapshot, and updates max sold count."""
    pack_category_name = "Unknown" # Default
    current_time_utc = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cur:
            series_id = pack_detail_data["id"] # Assumed to be present
            name = pack_detail_data.get("name", "Unknown Name")
            
            # Determine pack_category_name (e.g., "Diamond", "Emerald")
            if pack_detail_data.get("slabPackCategory") and isinstance(pack_detail_data["slabPackCategory"], dict):
                pack_category_name = pack_detail_data["slabPackCategory"].get("name", "Unknown Category")
            elif pack_detail_data.get("tier"): # Fallback if structure is different
                pack_category_name = pack_detail_data.get("tier", "Unknown Category")

            cost_from_api = pack_detail_data.get("costCents")
            if cost_from_api is None and pack_detail_data.get("slabPackCategory"):
                cost_from_api = pack_detail_data.get("slabPackCategory", {}).get("priceCents", 0)
            cost_from_api = cost_from_api if cost_from_api is not None else 0 # Ensure it's an int

            sold_count_api = pack_detail_data.get("packsSold", 0)
            total_count_api = pack_detail_data.get("packsTotal", 0)
            status = "active" if pack_detail_data.get("isActive", False) else "inactive"

            # Upsert pack_series_metadata
            cur.execute(
                """
                INSERT INTO pack_series_metadata (series_id, name, tier, cost_cents, status, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    tier = EXCLUDED.tier,
                    cost_cents = EXCLUDED.cost_cents,
                    status = EXCLUDED.status,
                    last_seen = EXCLUDED.last_seen;
                """,
                (series_id, name, pack_category_name, cost_from_api, status, current_time_utc)
            )

            # Insert into pack_snapshots (current sales numbers)
            cur.execute(
                "INSERT INTO pack_snapshots (series_id, packs_sold, packs_total, snapshot_time) VALUES (%s, %s, %s, %s);",
                (series_id, sold_count_api, total_count_api, current_time_utc)
            )

            # Update pack_max_sold
            cur.execute("SELECT max_sold FROM pack_max_sold WHERE series_id = %s FOR UPDATE;", (series_id,)) # Lock row
            result = cur.fetchone()
            if result is None:
                cur.execute("INSERT INTO pack_max_sold (series_id, max_sold, last_updated) VALUES (%s, %s, %s);",
                            (series_id, sold_count_api, current_time_utc))
            elif isinstance(sold_count_api, int) and (result[0] is None or sold_count_api > result[0]):
                cur.execute("UPDATE pack_max_sold SET max_sold = %s, last_updated = %s WHERE series_id = %s;",
                            (sold_count_api, current_time_utc, series_id))
        conn.commit()
    except Exception as e:
        print(f"[{current_time_utc.isoformat()}] ERROR in store_metadata_and_sales_snapshot for series {pack_detail_data.get('id', 'N/A')}: {e}")
        if conn: conn.rollback()
    return pack_category_name


def get_series_last_processed_time(conn, series_id):
    """Fetches the last successful processing timestamp for hit feed verification from series_processing_state."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT last_snapshot_cards_processed_at FROM series_processing_state WHERE series_id = %s;", (str(series_id),))
            result = cur.fetchone()
            if result and result[0]:
                # Ensure the fetched timestamp is timezone-aware (UTC)
                timestamp = result[0]
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                return timestamp
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR fetching last processed time for series {series_id}: {e}")
    return None

def update_series_last_processed_time(conn, series_id, process_time_utc):
    """Updates the last successful processing timestamp in series_processing_state."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO series_processing_state (series_id, last_snapshot_cards_processed_at)
                VALUES (%s, %s) ON CONFLICT (series_id) DO UPDATE SET
                    last_snapshot_cards_processed_at = EXCLUDED.last_snapshot_cards_processed_at;
                """, (str(series_id), process_time_utc)
            )
        conn.commit()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR updating last processed time for series {series_id}: {e}")

def verify_sale_on_hit_feed(card_to_verify, hit_feed_items, series_last_processed_time_utc):
    """Checks if a card is on the hit feed *after* it was last seen/processed."""
    if not hit_feed_items: return None # No items from hit feed API
    
    card_id_to_check_str = str(card_to_verify.get("card_id")) # card_id from pack_card_snapshots
    if card_id_to_check_str == "None":
        print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Cannot verify sale, card_to_verify missing 'card_id'. Details: {card_to_verify}")
        return None

    for hit_item in hit_feed_items:
        hit_card_id_str = str(hit_item.get("cardId")) # cardId from hit feed API
        if hit_card_id_str == card_id_to_check_str:
            hit_timestamp_str = hit_item.get("createdAt")
            if not hit_timestamp_str:
                print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Hit for card {card_id_to_check_str} (Hit ID: {hit_item.get('id')}) has no createdAt timestamp. Skipping.")
                continue
            try:
                hit_timestamp_utc = parser.isoparse(hit_timestamp_str)
                if hit_timestamp_utc.tzinfo is None: # Ensure it's timezone-aware (UTC)
                    hit_timestamp_utc = hit_timestamp_utc.replace(tzinfo=timezone.utc)

                if series_last_processed_time_utc:
                    if hit_timestamp_utc > series_last_processed_time_utc:
                        print(f"[{datetime.now(timezone.utc).isoformat()}] VERIFIED: Card ID {card_id_to_check_str} found on hit feed at {hit_timestamp_str} (after {series_last_processed_time_utc}).")
                        return hit_item # Return the full hit item
                else:
                    # No last processed time, means it's likely the first run for this series or state tracking failed.
                    # Consider any recent hit as a potential match. This is less precise.
                    # You might add a time window check here (e.g., hit within last X hours)
                    print(f"[{datetime.now(timezone.utc).isoformat()}] INFO: Card ID {card_id_to_check_str} found on hit feed at {hit_timestamp_str}. No series_last_processed_time for precise timing. Assuming verified for now.")
                    return hit_item
            except Exception as e:
                print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR parsing/comparing timestamp for card {card_id_to_check_str}. Hit ID: {hit_item.get('id')}. Error: {e}")
    return None # Not found or not within the correct time window

def log_suspected_swap(conn, series_id, card_details):
    """Logs a card that disappeared but wasn't confirmed on hit feed."""
    current_time_utc = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO suspected_swapped_cards 
                    (series_id, card_id, snapshot_tier, snapshot_player_name, snapshot_estimated_value_cents, disappeared_at)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (str(series_id), str(card_details.get('card_id')), card_details.get('tier'), 
                 card_details.get('player_name'), card_details.get('estimated_value_cents'), current_time_utc)
            )
        conn.commit()
        print(f"[{current_time_utc.isoformat()}] Logged suspected swap for card ID {card_details.get('card_id')} in series {series_id}.")
    except Exception as e:
        print(f"[{current_time_utc.isoformat()}] ERROR logging suspected swap for card ID {card_details.get('card_id')}: {e}")


def compute_and_store_sold_cards(conn, series_id, current_cards_with_tier_info, series_last_processed_time_utc):
    """Compares current pack inventory against previous, records sales, logs swaps."""
    current_card_ids_set = set(str(card["id"]) for card in current_cards_with_tier_info if "id" in card)
    
    # Fetch previous card snapshot for this series
    prev_card_data_map = {}
    prev_card_ids_set = set()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pack_card_snapshots WHERE series_id = %s;", (str(series_id),))
            prev_snapshots_rows = cur.fetchall()
            if prev_snapshots_rows:
                column_names = [desc[0] for desc in cur.description] if cur.description else []
                if column_names:
                    for row_data in prev_snapshots_rows:
                        card_dict = dict(zip(column_names, row_data))
                        card_id_str = str(card_dict.get("card_id"))
                        if card_id_str != "None": # Ensure we have a valid card_id
                            prev_card_ids_set.add(card_id_str)
                            prev_card_data_map[card_id_str] = card_dict
                else:
                    print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Could not get column names for pack_card_snapshots for series {series_id}.")
            else:
                print(f"[{datetime.now(timezone.utc).isoformat()}] INFO: No previous card snapshot found for series {series_id}. Assuming all current cards are new.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR fetching previous card snapshot for series {series_id}: {e}")
        return 0 # Cannot proceed without previous snapshot

    potential_sold_card_ids = prev_card_ids_set - current_card_ids_set
    confirmed_sold_cards_for_db_insert = []
    newly_confirmed_sold_count = 0
    
    hit_feed_api_items = [] # Initialize to empty list
    # Check if any of the potentially sold cards are of a tier that requires verification
    needs_hit_feed_check = any(
        prev_card_data_map.get(card_id, {}).get("tier") in TIERS_TO_VERIFY_ON_HIT_FEED
        for card_id in potential_sold_card_ids
    )

    if potential_sold_card_ids and needs_hit_feed_check:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Potential sales include verifiable tiers for series {series_id}. Fetching hit feed.")
        hit_feed_api_items = fetch_hit_feed_data_api() # Fetch latest hits from API

    for card_id_disappeared_str in potential_sold_card_ids:
        card_details_from_snapshot = prev_card_data_map.get(card_id_disappeared_str, {})
        if not card_details_from_snapshot: # Should not happen if logic is correct
            print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Card ID {card_id_disappeared_str} was in potential_sold_card_ids but not in prev_card_data_map.")
            continue

        card_tier_from_snapshot = card_details_from_snapshot.get("tier")
        
        verified_hit_data_from_api = None
        is_sale_hit_feed_verified = False

        if card_tier_from_snapshot in TIERS_TO_VERIFY_ON_HIT_FEED:
            verified_hit_data_from_api = verify_sale_on_hit_feed(card_details_from_snapshot, hit_feed_api_items, series_last_processed_time_utc)
            if verified_hit_data_from_api:
                is_sale_hit_feed_verified = True
            else:
                # Card of a verifiable tier disappeared but not found on hit feed -> likely a swap
                print(f"[{datetime.now(timezone.utc).isoformat()}] INFO: Card ID {card_id_disappeared_str} (Tier: {card_tier_from_snapshot}) from series {series_id} likely SWAPPED (not verified on hit feed).")
                log_suspected_swap(conn, series_id, card_details_from_snapshot)
                continue # Do not record this as a sale in sold_card_events
        
        # If execution reaches here, it's either:
        # 1. A card of a non-verifiable tier disappeared (assumed sold).
        # 2. A card of a verifiable tier disappeared AND was confirmed on the hit feed.
        newly_confirmed_sold_count += 1
        
        # Determine sold_at timestamp
        sold_at_timestamp_utc = datetime.now(timezone.utc) # Default for non-verified or if timestamp missing from hit
        if verified_hit_data_from_api and verified_hit_data_from_api.get('createdAt'):
            try:
                sold_at_timestamp_utc = parser.isoparse(verified_hit_data_from_api['createdAt'])
                if not sold_at_timestamp_utc.tzinfo: # Ensure timezone aware
                    sold_at_timestamp_utc = sold_at_timestamp_utc.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Could not parse createdAt '{verified_hit_data_from_api['createdAt']}' for hit {verified_hit_data_from_api.get('id')}. Using current time. Error: {e}")
                # sold_at_timestamp_utc remains current time

        # Prepare data tuple for insertion, carefully matching schema.sql
        snapshot_overall_val = card_details_from_snapshot.get('overall')
        snapshot_overall_float = float(snapshot_overall_val) if snapshot_overall_val is not None else None
        
        hit_feed_overall_val = verified_hit_data_from_api.get('overall') if verified_hit_data_from_api else None
        hit_feed_overall_float = float(hit_feed_overall_val) if hit_feed_overall_val is not None else None

        data_tuple_for_insert = (
            str(series_id), str(card_id_disappeared_str),
            # Snapshot data
            card_details_from_snapshot.get("tier"), 
            card_details_from_snapshot.get("estimated_value_cents"),
            card_details_from_snapshot.get("player_name"), 
            card_details_from_snapshot.get("set_name"),
            card_details_from_snapshot.get("insert_name"), 
            card_details_from_snapshot.get("grading_company"), 
            snapshot_overall_float,
            # Hit Feed data (null if not verified_hit_data_from_api)
            verified_hit_data_from_api.get('id') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('hitRate') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('username') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('avatarUrl') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('number') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('tag') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('playerName') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('setName') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('setNumber') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('parallelName') if verified_hit_data_from_api else None,
            str(verified_hit_data_from_api.get('parallelNumber')) if verified_hit_data_from_api and verified_hit_data_from_api.get('parallelNumber') is not None else None,
            str(verified_hit_data_from_api.get('parallelTotal')) if verified_hit_data_from_api and verified_hit_data_from_api.get('parallelTotal') is not None else None,
            verified_hit_data_from_api.get('frontSlabPictureUrl') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('backSlabPictureUrl') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('gradingCompany') if verified_hit_data_from_api else None,
            hit_feed_overall_float,
            verified_hit_data_from_api.get('insert') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('arenaClubOfferStatus') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('slabPackSeriesName') if verified_hit_data_from_api else None,
            verified_hit_data_from_api.get('slabPackCategoryName') if verified_hit_data_from_api else None,
            sold_at_timestamp_utc,
            is_sale_hit_feed_verified
        )
        confirmed_sold_cards_for_db_insert.append(data_tuple_for_insert)

    # Batch insert confirmed sales
    if confirmed_sold_cards_for_db_insert:
        try:
            with conn.cursor() as cur:
                insert_query_sold_events = """
                    INSERT INTO sold_card_events (
                        series_id, card_id, 
                        snapshot_tier, snapshot_estimated_value_cents, snapshot_player_name, snapshot_set_name,
                        snapshot_insert_name, snapshot_grading_company, snapshot_overall,
                        hit_feed_event_id, hit_rate, hit_feed_username, hit_feed_avatar_url,
                        hit_feed_number, hit_feed_tag, hit_feed_player_name, hit_feed_set_name,
                        hit_feed_set_number, hit_feed_parallel_name, hit_feed_parallel_number,
                        hit_feed_parallel_total, hit_feed_front_image_url, hit_feed_back_image_url,
                        hit_feed_grading_company, hit_feed_overall, hit_feed_insert_name,
                        hit_feed_arena_club_offer_status, hit_feed_slab_pack_series_name, 
                        hit_feed_slab_pack_category_name, sold_at, is_hit_feed_verified
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s 
                    ) ON CONFLICT (hit_feed_event_id) WHERE hit_feed_event_id IS NOT NULL DO NOTHING;
                """ # 31 placeholders
                cur.executemany(insert_query_sold_events, confirmed_sold_cards_for_db_insert)
                print(f"[{datetime.now(timezone.utc).isoformat()}] Attempted to store {len(confirmed_sold_cards_for_db_insert)} sold cards for series {series_id}. Affected rows: {cur.rowcount}")
                
                if newly_confirmed_sold_count > 0: # Only update tracker if actual sales were recorded
                    update_sales_tracker_query = """
                        INSERT INTO pack_sales_tracker (series_id, total_sold, last_checked) VALUES (%s, %s, NOW())
                        ON CONFLICT (series_id) DO UPDATE SET
                            total_sold = pack_sales_tracker.total_sold + EXCLUDED.total_sold, last_checked = NOW();"""
                    cur.execute(update_sales_tracker_query, (str(series_id), newly_confirmed_sold_count))
            conn.commit()
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR batch inserting sold cards for series {series_id}: {e}")
            if conn: conn.rollback()
    
    # Update current snapshot of cards in pack (pack_card_snapshots)
    time_of_current_snapshot = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cur:
            # Delete old snapshots for this series
            cur.execute("DELETE FROM pack_card_snapshots WHERE series_id = %s;", (str(series_id),))
            
            # Prepare new snapshot data
            snapshot_values_to_insert = []
            if current_cards_with_tier_info:
                for card_api_data in current_cards_with_tier_info:
                    if "id" not in card_api_data: continue # Skip if no card ID
                    
                    overall_val = card_api_data.get("overall")
                    overall_float = float(overall_val) if overall_val is not None else None
                    
                    snapshot_values_to_insert.append((
                        str(series_id), str(card_api_data["id"]), card_api_data.get("tier_name"), # tier_name from processing
                        card_api_data.get("playerName"), overall_float,
                        card_api_data.get("insert"), card_api_data.get("setNumber"),
                        card_api_data.get("setName"), card_api_data.get("holo"),
                        card_api_data.get("rarity"),
                        str(card_api_data.get("parallelNumber")) if card_api_data.get("parallelNumber") is not None else None,
                        str(card_api_data.get("parallelTotal")) if card_api_data.get("parallelTotal") is not None else None,
                        card_api_data.get("parallelName"),
                        card_api_data.get("frontSlabPictureUrl"), card_api_data.get("backSlabPictureUrl"),
                        card_api_data.get("slabKind"), card_api_data.get("gradingCompany"),
                        card_api_data.get("estimatedValueCents"),
                        time_of_current_snapshot # The time this snapshot is being recorded
                    ))
            
            if snapshot_values_to_insert:
                insert_snapshot_query = """
                    INSERT INTO pack_card_snapshots (
                        series_id, card_id, tier, player_name, overall, insert_name, set_number, set_name, 
                        holo, rarity, parallel_number, parallel_total, parallel_name, front_image, 
                        back_image, slab_kind, grading_company, estimated_value_cents, snapshot_time
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                """ # 19 placeholders
                cur.executemany(insert_snapshot_query, snapshot_values_to_insert)
        conn.commit()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR updating pack_card_snapshots for series {series_id}: {e}")
        if conn: conn.rollback()
        
    return newly_confirmed_sold_count


def store_pack_total_value_snapshot(conn, series_id, total_value_cents):
    """Stores a snapshot of the sum of all available cards' values in the pack."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pack_total_value_snapshots (series_id, total_estimated_value_cents, snapshot_time) VALUES (%s, %s, NOW());",
                (str(series_id), total_value_cents)
            )
        conn.commit()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR storing total pack value for series {series_id}: {e}")
        if conn: conn.rollback()

def calculate_and_store_ev_roi(conn, series_id, pack_category_from_meta, detailed_pack_data):
    """Calculates EV and ROI based on tier hit rates and stores them."""
    num_premium_cards_per_pack = detailed_pack_data.get("numPremiumCardsPerPack", 0)
    num_non_premium_cards_per_pack = detailed_pack_data.get("numNonPremiumCardsPerPack", 0)

    ev_premium_slot_total_cents = 0.0
    ev_non_premium_slot_total_cents = 0.0
    tier_contributions_for_db = []

    for tier_info in detailed_pack_data.get("slabPackTiers", []):
        try:
            hit_rate = float(tier_info.get("hitRate", 0.0))
        except (ValueError, TypeError):
            hit_rate = 0.0
            print(f"WARN: Invalid or missing hitRate for tier {tier_info.get('name')} in series {series_id}. Defaulting to 0.0.")

        cards_in_tier = tier_info.get("cards", [])
        num_cards_in_this_tier = len(cards_in_tier)
        sum_value_in_tier_cents = 0
        for card_data in cards_in_tier:
            val = card_data.get("estimatedValueCents")
            sum_value_in_tier_cents += val if isinstance(val, (int, float)) else 0
        
        avg_value_in_tier_cents = float(sum_value_in_tier_cents) / num_cards_in_this_tier if num_cards_in_this_tier > 0 else 0.0
        tier_ev_contribution_cents = avg_value_in_tier_cents * hit_rate

        tier_contributions_for_db.append({
            "tier_api_id": tier_info.get("id"), 
            "tier_name": tier_info.get("name", "Unknown Tier"),
            "is_premium": tier_info.get("isPremium", False), 
            "hit_rate": hit_rate,
            "num_cards_in_tier": num_cards_in_this_tier, 
            "avg_value_in_tier_cents": round(avg_value_in_tier_cents),
            "tier_contribution_to_ev_cents": round(tier_ev_contribution_cents)
        })

        if tier_info.get("isPremium", False):
            ev_premium_slot_total_cents += tier_ev_contribution_cents
        else:
            ev_non_premium_slot_total_cents += tier_ev_contribution_cents

    expected_value_total_cents = round(
        (ev_premium_slot_total_cents * num_premium_cards_per_pack) + 
        (ev_non_premium_slot_total_cents * num_non_premium_cards_per_pack)
    )

    static_pack_cost_val = get_static_pack_cost(pack_category_from_meta)
    current_roi = None # Default ROI
    if static_pack_cost_val is not None and static_pack_cost_val > 0:
        current_roi = (float(expected_value_total_cents) / static_pack_cost_val) - 1.0
    elif static_pack_cost_val == 0:
        current_roi = float("inf") # Or handle as per desired logic
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pack_ev_roi_snapshots 
                    (series_id, expected_value_cents, static_pack_cost_cents, roi, 
                     num_premium_cards_per_pack, num_non_premium_cards_per_pack, snapshot_time)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING snapshot_id;""",
                (str(series_id), expected_value_total_cents, static_pack_cost_val, current_roi, 
                 num_premium_cards_per_pack, num_non_premium_cards_per_pack)
            )
            ev_roi_snapshot_id = cur.fetchone()[0]

            if ev_roi_snapshot_id and tier_contributions_for_db:
                contributions_to_insert_tuples = []
                for tc in tier_contributions_for_db:
                    contributions_to_insert_tuples.append((
                        str(series_id), ev_roi_snapshot_id, tc["tier_api_id"], tc["tier_name"], 
                        tc["is_premium"], tc["hit_rate"], tc["num_cards_in_tier"], 
                        tc["avg_value_in_tier_cents"], tc["tier_contribution_to_ev_cents"],
                        datetime.now(timezone.utc) # snapshot_time for this contribution
                    ))
                
                tier_contribution_insert_query = """
                    INSERT INTO pack_tier_ev_contribution_snapshots (
                        series_id, ev_roi_snapshot_id, tier_api_id, tier_name, is_premium, 
                        hit_rate, num_cards_in_tier, avg_value_in_tier_cents, 
                        tier_contribution_to_ev_cents, snapshot_time
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """ # 10 placeholders
                cur.executemany(tier_contribution_insert_query, contributions_to_insert_tuples)
        conn.commit()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR storing EV/ROI data for series {series_id}: {e}")
        if conn: conn.rollback()


def wait_for_postgres(retries=30, delay=2):
    """Waits for the PostgreSQL database to be ready."""
    for i in range(retries):
        try:
            conn_pg = get_db_connection()
            if conn_pg:
                conn_pg.close()
                print(f"[{datetime.now(timezone.utc).isoformat()}] Postgres is ready.")
                return True
        except psycopg2.OperationalError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Waiting for Postgres ({i + 1}/{retries})...")
            time.sleep(delay)
    print(f"[{datetime.now(timezone.utc).isoformat()}] Postgres not ready after multiple attempts.")
    return False

# --- Main Tracker Logic ---
def run_tracker():
    print(f"[{datetime.now(timezone.utc).isoformat()}] FlipForce tracker service started.")
    db_conn = None
    try:
        db_conn = get_db_connection()
        if not db_conn:
            print(f"[{datetime.now(timezone.utc).isoformat()}] CRITICAL: Failed to establish initial DB connection. Exiting.")
            return

        while True:
            current_processing_cycle_start_time_utc = datetime.now(timezone.utc)
            print(f"[{current_processing_cycle_start_time_utc.isoformat()}] Starting new processing cycle for targeted packs.")
            
            all_categories_data = fetch_all_pack_data_from_categories_endpoint()
            if not all_categories_data or "items" not in all_categories_data:
                print(f"[{datetime.now(timezone.utc).isoformat()}] Could not fetch or parse categories overview. Retrying in 60 seconds.")
                time.sleep(60)
                continue

            discovered_series_to_process_details = []
            for target_pack_config in TARGET_PACKS_TO_TRACK:
                found_series_id_for_this_target = None
                target_category_name_lower = target_pack_config["category_name"].lower()
                target_series_name_lower = target_pack_config["series_name"].lower()

                for category_from_api in all_categories_data.get("items", []):
                    if category_from_api.get("name", "").lower() == target_category_name_lower:
                        for series_in_category in category_from_api.get("slabPackSeries", []):
                            if series_in_category.get("name", "").lower() == target_series_name_lower:
                                found_series_id_for_this_target = series_in_category.get("id")
                                if found_series_id_for_this_target:
                                    discovered_series_to_process_details.append({
                                        "id": str(found_series_id_for_this_target), # Store as string
                                        "category_name_from_config": target_pack_config["category_name"],
                                        "series_name_from_config": target_pack_config["series_name"]
                                    })
                                break # Found series in this category, move to next series in category
                        if found_series_id_for_this_target: # If found for this target, no need to check other API categories
                            break 
                if not found_series_id_for_this_target:
                    print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: Could not find series_id for target config: {target_pack_config['category_name']} - {target_pack_config['series_name']}")

            if not discovered_series_to_process_details:
                print(f"[{datetime.now(timezone.utc).isoformat()}] No series IDs found for targeted packs in this cycle. Waiting 5 minutes...")
                time.sleep(300) # 5 minutes
                continue

            for series_info in discovered_series_to_process_details:
                series_id_str = series_info["id"] # Already string
                print(f"\n--- [{datetime.now(timezone.utc).isoformat()}] Processing Series ID: {series_id_str} ({series_info['category_name_from_config']} - {series_info['series_name_from_config']}) ---")
                
                detailed_pack_data_from_api = fetch_slab_pack(series_id_str)
                if not detailed_pack_data_from_api or not detailed_pack_data_from_api.get("id"):
                    print(f"[{datetime.now(timezone.utc).isoformat()}] No detailed pack data fetched for series ID {series_id_str}. Skipping.")
                    time.sleep(1) # Small delay before next series
                    continue
                
                # Ensure authoritative_series_id is a string for all DB operations
                authoritative_series_id_str = str(detailed_pack_data_from_api["id"])
                
                # Get the last processed time for this series to use for hit feed verification
                # This timestamp marks the end of the previous successful card snapshot processing for this series.
                series_last_snapshot_processed_at_utc = get_series_last_processed_time(db_conn, authoritative_series_id_str)
                print(f"[{datetime.now(timezone.utc).isoformat()}] Last snapshot processed time for series {authoritative_series_id_str}: {series_last_snapshot_processed_at_utc}")

                pack_category_name_from_meta = store_metadata_and_sales_snapshot(db_conn, detailed_pack_data_from_api)
                
                # Prepare list of all cards currently in the pack for various calculations
                all_cards_in_current_pack_snapshot = []
                current_total_sum_of_card_values_cents = 0
                for tier_data_from_api in detailed_pack_data_from_api.get("slabPackTiers", []):
                    tier_name_for_card_in_tier = tier_data_from_api.get("name", "Unknown Tier")
                    for card_api_item in tier_data_from_api.get("cards", []):
                        card_copy_for_processing = card_api_item.copy()
                        card_copy_for_processing["tier_name"] = tier_name_for_card_in_tier # Add tier_name for context
                        all_cards_in_current_pack_snapshot.append(card_copy_for_processing)
                        
                        card_value_cents = card_api_item.get("estimatedValueCents", 0)
                        current_total_sum_of_card_values_cents += card_value_cents if isinstance(card_value_cents, (int, float)) else 0
                
                store_pack_total_value_snapshot(db_conn, authoritative_series_id_str, current_total_sum_of_card_values_cents)
                calculate_and_store_ev_roi(db_conn, authoritative_series_id_str, pack_category_name_from_meta, detailed_pack_data_from_api)
                
                # This is a critical step: compute sales based on disappearance and hit feed verification
                confirmed_sold_this_run = compute_and_store_sold_cards(
                    db_conn, 
                    authoritative_series_id_str, 
                    all_cards_in_current_pack_snapshot, 
                    series_last_snapshot_processed_at_utc # Pass the correct timestamp
                )
                
                # Update the last processed time for this series to the start time of THIS cycle,
                # or more accurately, the timestamp of the pack_card_snapshot just written.
                # Using current_processing_cycle_start_time_utc is a safe bet for "since when" for the *next* run.
                update_series_last_processed_time(db_conn, authoritative_series_id_str, current_processing_cycle_start_time_utc) 

                pack_name_display = detailed_pack_data_from_api.get('name', 'N/A Pack Name')
                print(f"[{datetime.now(timezone.utc).isoformat()}] Completed processing for: {pack_name_display} (ID: {authoritative_series_id_str}) | Category: {pack_category_name_from_meta} | Confirmed Sold This Run: {confirmed_sold_this_run} | Sum of Available Cards Value: ${current_total_sum_of_card_values_cents/100:.2f}")
                time.sleep(2) # Brief pause between processing different series

            print(f"[{datetime.now(timezone.utc).isoformat()}] Completed processing all targeted series for this iteration. Waiting 5 seconds before next cycle...")
            time.sleep(5) # Wait before starting the whole process over

    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Tracker stopped by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] UNEXPECTED FATAL ERROR in run_tracker: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db_conn:
            try:
                db_conn.close()
                print(f"[{datetime.now(timezone.utc).isoformat()}] Database connection closed at end of run_tracker or in finally block.")
            except Exception as db_close_e:
                print(f"[{datetime.now(timezone.utc).isoformat()}] Error closing database connection in finally block: {db_close_e}")

if __name__ == "__main__":
    if not wait_for_postgres():
        print(f"[{datetime.now(timezone.utc).isoformat()}] Exiting tracker as Postgres is not available after multiple retries.")
        exit(1) # Exit if DB is not ready

    # Initialize schema
    conn_for_schema_run = None
    try:
        conn_for_schema_run = get_db_connection()
        if conn_for_schema_run:
            run_schema_sql(conn_for_schema_run) # This will raise an exception if it fails catastrophically
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] CRITICAL: Failed to get DB connection for schema setup. Exiting tracker.")
            exit(1) # Exit if schema connection fails
    except Exception as schema_setup_error:
        # run_schema_sql already prints, this is just to confirm exit
        print(f"[{datetime.now(timezone.utc).isoformat()}] Exiting tracker due to error during schema setup: {schema_setup_error}")
        exit(1) # Exit if schema setup fails
    finally:
        if conn_for_schema_run:
            conn_for_schema_run.close()
    
    # Start the main tracking loop
    run_tracker()
