import os
import time
from datetime import datetime

import psycopg2
import requests
from config import get_db_connection

# Moved print statements to after all imports
print("[TrackerDiag] tracker.py execution started - TOP OF FILE")
print("[Tracker] ✅ tracker.py has started.")

# Define the packs you want to track by their category and series name
# These names should match what's returned by the /slab-pack-categories API endpoint.
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

# Static pack costs in cents for ROI calculation
STATIC_PACK_COSTS_CENTS = {
    "Diamond": 100000,  # $1,000
    "Emerald": 50000,   # $500
    "Ruby": 25000,      # $250
    "Gold": 10000,      # $100
    "Silver": 5000,     # $50
    "Misc.": 2500,      # $25 (Matches API example "Misc.")
    "Misc": 2500,       # Fallback for "Misc" if API varies
}

def get_static_pack_cost(pack_category_name):
    """Gets the static cost for a given pack category name."""
    if not pack_category_name:
        return None
    cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name)
    if cost is None: # Try matching common variations if direct match fails
        if pack_category_name.endswith('.'):
            cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name[:-1])
        else:
            cost = STATIC_PACK_COSTS_CENTS.get(pack_category_name + '.')
    return cost


def fetch_all_pack_data_from_categories_endpoint():
    """
    Fetches the complete list of pack categories and their associated series from the
    Arena Club API.
    """
    try:
        print(
            f"[{datetime.now()}] Fetching all pack categories from "
            f"{SLAB_PACK_CATEGORIES_URL}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://arenaclub.com/",
            "Origin": "https://arenaclub.com",
        }
        response = requests.get(SLAB_PACK_CATEGORIES_URL, headers=headers, timeout=30)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX/5XX)
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_message = (
            f"[{datetime.now()}] HTTP error fetching all pack categories: {e}. "
            f"Response: {e.response.text if e.response else 'No response'}"
        )
        print(error_message)
    except Exception as e:
        # Catching a broad exception for other potential issues like network errors
        print(f"[{datetime.now()}] Error fetching all pack categories data: {e}")
    return None


def fetch_slab_pack(series_id):
    """
    Fetches detailed data for a specific slab pack series using its series ID.
    """
    api_url = f"{ARENA_CLUB_API_BASE_URL}{series_id}"
    try:
        print(
            f"[{datetime.now()}] Fetching detailed data for series: {series_id} "
            f"from {api_url}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()  # Checks for HTTP errors
        return response.json()
    except requests.exceptions.HTTPError as e:
        # Specific handling for HTTP errors to provide more context if available
        error_message = (
            f"[{datetime.now()}] HTTP error for series {series_id}: {e}. "
            f"Response: {e.response.text if e.response else 'No response'}"
        )
        print(error_message)
    except Exception as e:
        # General exception for other issues (e.g., network,
        # JSON parsing if not caught by response.json())
        print(
            f"[{datetime.now()}] Error fetching slab pack data for series "
            f"{series_id}: {e}"
        )
    return None


def run_schema_sql(conn):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r") as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"[{datetime.now()}] Schema loaded/verified.")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to run schema.sql: {e}")
        conn.rollback() 
        raise

# Combines metadata storage and sales snapshot storage
def store_metadata_and_sales_snapshot(conn, pack_detail_data):
    """Stores pack metadata, current sales snapshot, and updates max sold count.
    Returns the pack category name (e.g., "Diamond") from metadata.
    """
    pack_category_name = "Unknown" 
    with conn.cursor() as cur:
        series_id_from_pack = pack_detail_data["id"]
        name = pack_detail_data.get("name", "Unknown")

        # Determine pack_category_name (e.g., "Diamond", "Emerald")
        if pack_detail_data.get("slabPackCategory") and isinstance(pack_detail_data["slabPackCategory"], dict):
            pack_category_name = pack_detail_data["slabPackCategory"].get("name", "Unknown")
        elif pack_detail_data.get("tier"): # Fallback if structure is different for some reason
             pack_category_name = pack_detail_data.get("tier", "Unknown")

        # Cost from API (for storage in pack_series_metadata, may differ from static cost for ROI)
        cost_from_api = pack_detail_data.get("costCents")
        if cost_from_api is None and pack_detail_data.get("slabPackCategory"): # Check category level if not on series
            cost_from_api = pack_detail_data.get("slabPackCategory", {}).get("priceCents", 0)
        cost_from_api = cost_from_api if cost_from_api is not None else 0

        sold_count_api = pack_detail_data.get("packsSold", 0)
        total_count_api = pack_detail_data.get("packsTotal", 0)
        status = "active" if pack_detail_data.get("isActive") else "inactive"

        # Upsert pack_series_metadata
        cur.execute(
            """
            INSERT INTO pack_series_metadata
                (series_id, name, tier, cost_cents, status, last_seen)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (series_id) DO UPDATE SET
                name = EXCLUDED.name,
                tier = EXCLUDED.tier, 
                cost_cents = EXCLUDED.cost_cents, 
                status = EXCLUDED.status,
                last_seen = NOW();
            """,
            (series_id_from_pack, name, pack_category_name, cost_from_api, status),
        )

        # Insert into pack_snapshots (current sales numbers)
        cur.execute(
            """
            INSERT INTO pack_snapshots (series_id, packs_sold, packs_total)
            VALUES (%s, %s, %s);
            """,
            (series_id_from_pack, sold_count_api, total_count_api),
        )

        # Update pack_max_sold
        cur.execute(
            "SELECT max_sold FROM pack_max_sold WHERE series_id = %s;",
            (series_id_from_pack,),
        )
        result = cur.fetchone()
        if result is None:
            cur.execute(
                "INSERT INTO pack_max_sold (series_id, max_sold) VALUES (%s, %s);",
                (series_id_from_pack, sold_count_api),
            )
        elif (
            isinstance(sold_count_api, int)
            and result[0] is not None
            and sold_count_api > result[0]
        ):
            cur.execute(
                """
                UPDATE pack_max_sold
                SET max_sold = %s, last_updated = NOW()
                WHERE series_id = %s;
                """,
                (sold_count_api, series_id_from_pack),
            )
    conn.commit()
    return pack_category_name


def wait_for_postgres(retries=30, delay=2):
    """Waits for the PostgreSQL database to be ready."""
    for i in range(retries):
        try:
            conn_pg = get_db_connection()
            if conn_pg:
                conn_pg.close() # Successfully connected, close it
                print(f"[{datetime.now()}] Postgres is ready.")
                return True # Indicate success
        except psycopg2.OperationalError:
            print(f"[{datetime.now()}] Waiting for Postgres ({i + 1}/{retries})...")
            time.sleep(delay)
    print(f"[{datetime.now()}] Postgres not ready after multiple attempts.")
    return False # Indicate failure


def compute_and_store_sold_cards(conn, series_id, current_cards_with_tier_info):
    """
    Compares current pack card inventory against the previous snapshot to identify
    and record newly sold cards. Updates pack_card_snapshots and pack_sales_tracker.
    """
    current_card_ids = set(card["id"] for card in current_cards_with_tier_info if "id" in card)

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))
        prev_snapshots = cur.fetchall()
        # Ensure cur.description is not None before list comprehension
        column_names = [desc[0] for desc in cur.description] if cur.description else []
        
        prev_card_ids = set()
        prev_card_data_map = {}

        if column_names: # Proceed only if column names could be fetched
            for row_data in prev_snapshots:
                card_dict = dict(zip(column_names, row_data))
                if "card_id" in card_dict:
                    prev_card_ids.add(card_dict["card_id"])
                    prev_card_data_map[card_dict["card_id"]] = card_dict
                else:
                    # This log helps diagnose schema/data integrity issues
                    print(f"[ERROR] compute_and_store_sold_cards: 'card_id' not found in snapshot row for series {series_id}. Columns: {column_names}")
        
        sold_card_ids = prev_card_ids - current_card_ids
        newly_sold_count = len(sold_card_ids)

        if newly_sold_count > 0:
            enriched_sales = []
            for card_id_sold in sold_card_ids:
                c_data = prev_card_data_map.get(card_id_sold, {})
                enriched_sales.append((
                    series_id, card_id_sold, c_data.get("tier"), c_data.get("player_name"),
                    c_data.get("overall"), c_data.get("insert_name"), c_data.get("set_number"),
                    c_data.get("set_name"), c_data.get("holo"), c_data.get("rarity"),
                    c_data.get("parallel_number"), c_data.get("parallel_total"),
                    c_data.get("parallel_name"), c_data.get("front_image"), c_data.get("back_image"),
                    c_data.get("slab_kind"), c_data.get("grading_company"),
                    c_data.get("estimated_value_cents")
                ))
            if enriched_sales:
                cur.executemany("""
                    INSERT INTO sold_card_events (series_id, card_id, tier, player_name, overall, insert_name, set_number, set_name, holo, rarity, parallel_number, parallel_total, parallel_name, front_image, back_image, slab_kind, grading_company, estimated_value_cents, sold_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW());
                    """, enriched_sales)
            
            # Update pack_sales_tracker
            cur.execute("""
                INSERT INTO pack_sales_tracker (series_id, total_sold, last_checked) VALUES (%s, %s, NOW())
                ON CONFLICT (series_id) DO UPDATE SET total_sold = pack_sales_tracker.total_sold + EXCLUDED.total_sold, last_checked = NOW();
                """, (series_id, newly_sold_count))

        # Update current snapshot of cards in pack
        cur.execute("DELETE FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))
        snapshot_insert_values = []
        if current_cards_with_tier_info:
            for card_api_data in current_cards_with_tier_info:
                if "id" not in card_api_data: 
                    print(f"[ERROR] compute_and_store_sold_cards: Card data missing 'id' for series {series_id}: {card_api_data.get('playerName')}")
                    continue
                snapshot_insert_values.append((
                    series_id, card_api_data["id"], card_api_data.get("tier_name"), # tier_name was added during processing
                    card_api_data.get("playerName"), card_api_data.get("overall"),
                    card_api_data.get("insert"), card_api_data.get("setNumber"),
                    card_api_data.get("setName"), card_api_data.get("holo"),
                    card_api_data.get("rarity"), card_api_data.get("parallelNumber"),
                    card_api_data.get("parallelTotal"), card_api_data.get("parallelName"),
                    card_api_data.get("frontSlabPictureUrl"), card_api_data.get("backSlabPictureUrl"),
                    card_api_data.get("slabKind"), card_api_data.get("gradingCompany"),
                    card_api_data.get("estimatedValueCents")
                ))
            if snapshot_insert_values:
                cur.executemany("""
                    INSERT INTO pack_card_snapshots (series_id, card_id, tier, player_name, overall, insert_name, set_number, set_name, holo, rarity, parallel_number, parallel_total, parallel_name, front_image, back_image, slab_kind, grading_company, estimated_value_cents)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                    """, snapshot_insert_values)
    conn.commit()
    return newly_sold_count


def store_pack_total_value_snapshot(conn, series_id, total_value_cents):
    """Stores a snapshot of the sum of all available cards' values in the pack."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pack_total_value_snapshots (series_id, total_estimated_value_cents, snapshot_time) VALUES (%s, %s, NOW());",
                (series_id, total_value_cents)
            )
        conn.commit()
        # print(f"[{datetime.now()}] Recorded total available pack value for series {series_id}: {total_value_cents} cents.")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR storing total pack value for series {series_id}: {e}")
        if conn:
            try: conn.rollback()
            except Exception as rb_e: print(f"[{datetime.now()}] ERROR during rollback for total pack value: {rb_e}")

def calculate_and_store_ev_roi(conn, series_id, pack_category_from_meta, detailed_pack_data):
    """Calculates EV and ROI based on tier hit rates and stores them."""
    num_premium_cards_per_pack = detailed_pack_data.get("numPremiumCardsPerPack", 0)
    num_non_premium_cards_per_pack = detailed_pack_data.get("numNonPremiumCardsPerPack", 0)
    
    ev_premium_slot_total_cents = 0.0 # Use float for intermediate sum
    ev_non_premium_slot_total_cents = 0.0 # Use float for intermediate sum
    tier_contributions_for_db = []
    
    slab_pack_tiers_data = detailed_pack_data.get("slabPackTiers", [])

    for tier_info in slab_pack_tiers_data:
        tier_api_id = tier_info.get("id")
        tier_name = tier_info.get("name", "Unknown Tier")
        is_premium = tier_info.get("isPremium", False)
        # Ensure hitRate is float, default to 0.0 if missing or invalid
        try:
            hit_rate = float(tier_info.get("hitRate", 0.0))
        except (ValueError, TypeError):
            hit_rate = 0.0
            print(f"WARN: Invalid or missing hitRate for tier {tier_name} in series {series_id}. Defaulting to 0.0.")

        
        cards_in_tier = tier_info.get("cards", [])
        num_cards_in_this_tier = len(cards_in_tier)
        sum_value_in_tier_cents = 0
        
        if num_cards_in_this_tier > 0:
            for card_data in cards_in_tier:
                val = card_data.get("estimatedValueCents")
                sum_value_in_tier_cents += val if isinstance(val, (int, float)) else 0
            avg_value_in_tier_cents = float(sum_value_in_tier_cents) / num_cards_in_this_tier
        else:
            avg_value_in_tier_cents = 0.0
            
        tier_ev_contribution_cents = avg_value_in_tier_cents * hit_rate
        
        tier_contributions_for_db.append({
            'tier_api_id': tier_api_id, 'tier_name': tier_name,
            'is_premium': is_premium, 'hit_rate': hit_rate,
            'num_cards_in_tier': num_cards_in_this_tier,
            'avg_value_in_tier_cents': round(avg_value_in_tier_cents),
            'tier_contribution_to_ev_cents': round(tier_ev_contribution_cents)
        })
        
        if is_premium:
            ev_premium_slot_total_cents += tier_ev_contribution_cents
        else:
            ev_non_premium_slot_total_cents += tier_ev_contribution_cents
            
    expected_value_total_cents = round(
        (ev_premium_slot_total_cents * num_premium_cards_per_pack) + 
        (ev_non_premium_slot_total_cents * num_non_premium_cards_per_pack)
    )
    
    static_pack_cost_val = get_static_pack_cost(pack_category_from_meta)
    current_roi = 0.0 # Default ROI

    if static_pack_cost_val is not None and static_pack_cost_val > 0:
        current_roi = (float(expected_value_total_cents) / static_pack_cost_val) - 1.0
    elif static_pack_cost_val == 0:
        print(f"[{datetime.now()}] WARN: Static pack cost is 0 for category '{pack_category_from_meta}', series {series_id}. ROI is effectively infinite or undefined.")
        current_roi = float('inf') # Or handle as per desired logic, maybe None
    else: # static_pack_cost_val is None
        print(f"[{datetime.now()}] WARN: Static pack cost not found for category '{pack_category_from_meta}', series {series_id}. ROI cannot be calculated.")
        static_pack_cost_val = None # Ensure it's None if not found for DB
        current_roi = None


    # Store in DB
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pack_ev_roi_snapshots (series_id, expected_value_cents, static_pack_cost_cents, roi, num_premium_cards_per_pack, num_non_premium_cards_per_pack, snapshot_time)
                VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING snapshot_id;
                """,
                (series_id, expected_value_total_cents, static_pack_cost_val, current_roi, num_premium_cards_per_pack, num_non_premium_cards_per_pack)
            )
            ev_roi_snapshot_id = cur.fetchone()[0]

            if ev_roi_snapshot_id and tier_contributions_for_db:
                contributions_to_insert = []
                for tc in tier_contributions_for_db:
                    contributions_to_insert.append((
                        series_id, ev_roi_snapshot_id, tc['tier_api_id'], tc['tier_name'],
                        tc['is_premium'], tc['hit_rate'], tc['num_cards_in_tier'],
                        tc['avg_value_in_tier_cents'], tc['tier_contribution_to_ev_cents']
                    ))
                
                cur.executemany(
                    """
                    INSERT INTO pack_tier_ev_contribution_snapshots (series_id, ev_roi_snapshot_id, tier_api_id, tier_name, is_premium, hit_rate, num_cards_in_tier, avg_value_in_tier_cents, tier_contribution_to_ev_cents, snapshot_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    contributions_to_insert
                )
            conn.commit()
            # print(f"[{datetime.now()}] Stored EV/ROI for {series_id}: EV ${expected_value_total_cents/100:.2f}, ROI {current_roi if current_roi is not None else 'N/A'}")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR storing EV/ROI data for {series_id}: {e}")
        conn.rollback()


def run_tracker():
    print(f"[{datetime.now()}] FlipForce tracker started for targeted packs.")
    db_conn = None
    try:
        db_conn = get_db_connection()
        if not db_conn:
            print(f"[{datetime.now()}] CRITICAL: Failed to establish initial DB connection. Exiting.")
            return

        while True:
            all_categories_data = fetch_all_pack_data_from_categories_endpoint()
            if not all_categories_data or "items" not in all_categories_data:
                print(f"[{datetime.now()}] Could not fetch or parse categories overview. Retrying in 60s.")
                time.sleep(60)
                continue

            discovered_series_to_process = []
            for target_pack in TARGET_PACKS_TO_TRACK:
                found_series_id_for_target = None
                target_cat_name_lower = target_pack["category_name"].lower()
                target_series_name_lower = target_pack["series_name"].lower()
                for category_from_api in all_categories_data.get("items", []):
                    if category_from_api.get("name", "").lower() == target_cat_name_lower:
                        for series_in_category in category_from_api.get("slabPackSeries", []):
                            if series_in_category.get("name", "").lower() == target_series_name_lower:
                                found_series_id_for_target = series_in_category.get("id")
                                if found_series_id_for_target:
                                    discovered_series_to_process.append({
                                        "id": found_series_id_for_target,
                                        "category_name_log": category_from_api.get("name"), 
                                        "series_name_log": series_in_category.get("name"), 
                                    })
                                break
                        if found_series_id_for_target: break
                if not found_series_id_for_target:
                    print(f"WARN: Could not find series_id for target: {target_pack['category_name']} - {target_pack['series_name']}")
            
            if not discovered_series_to_process:
                print(f"[{datetime.now()}] No series IDs found for targeted packs in this cycle. Waiting 5 minutes...")
                time.sleep(300) 
                continue

            for series_info in discovered_series_to_process:
                current_series_id_from_discovery = series_info["id"]
                detailed_pack_data = fetch_slab_pack(current_series_id_from_discovery)

                if detailed_pack_data and detailed_pack_data.get("id"):
                    authoritative_series_id = detailed_pack_data["id"]
                    
                    # Store metadata and get pack category (e.g., "Diamond")
                    pack_category_from_meta = store_metadata_and_sales_snapshot(db_conn, detailed_pack_data)
                    
                    # Prepare list of all cards currently in the pack for various calculations
                    all_cards_current_snapshot_for_processing = []
                    current_sum_of_all_card_values_cents = 0 

                    for tier_data in detailed_pack_data.get("slabPackTiers", []):
                        tier_name_for_card = tier_data.get("name", "Unknown Tier")
                        for card in tier_data.get("cards", []):
                            card_copy = card.copy()
                            card_copy["tier_name"] = tier_name_for_card 
                            all_cards_current_snapshot_for_processing.append(card_copy)
                            
                            val = card.get("estimatedValueCents", 0)
                            current_sum_of_all_card_values_cents += val if isinstance(val, (int, float)) else 0
                    
                    # Store the sum of all *available* cards' values (for historical pack value)
                    store_pack_total_value_snapshot(db_conn, authoritative_series_id, current_sum_of_all_card_values_cents)
                    
                    # Calculate and store EV and ROI based on hit rates
                    calculate_and_store_ev_roi(db_conn, authoritative_series_id, pack_category_from_meta, detailed_pack_data)
                    
                    # Compute newly sold cards and update the pack_card_snapshots table
                    sold_count = compute_and_store_sold_cards(db_conn, authoritative_series_id, all_cards_current_snapshot_for_processing)
                    
                    print(
                        f"[{datetime.now()}] Processed: {detailed_pack_data.get('name', 'N/A')} (ID: {authoritative_series_id}) | "
                        f"Category: {pack_category_from_meta} | Sold this run: {sold_count} | "
                        f"Sum Value of Avail. Cards: ${current_sum_of_all_card_values_cents / 100:.2f}"
                    )

                else:
                    print(f"[{datetime.now()}] No detailed data fetched for series ID {current_series_id_from_discovery}. Skipping.")
                time.sleep(5) 

            print(f"[{datetime.now()}] Completed processing all targeted series for this iteration. Waiting 5 seconds before next cycle...")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"[{datetime.now()}] Tracker stopped by user.")
    except Exception as e:
        print(f"[{datetime.now()}] UNEXPECTED ERROR in run_tracker: {e}")
        import traceback
        traceback.print_exc()
        if db_conn:
            try:
                db_conn.close()
                print(f"[{datetime.now()}] DB connection closed due to error in run_tracker.")
            except Exception as db_close_e:
                print(f"[{datetime.now()}] Further error closing DB during exception handling: {db_close_e}")
            db_conn = None 
    finally:
        if db_conn:
            try:
                db_conn.close()
                print(f"[{datetime.now()}] Database connection closed normally at end of run_tracker or in finally.")
            except Exception as e:
                print(f"[{datetime.now()}] Error closing database connection in finally block: {e}")


if __name__ == "__main__":
    if not wait_for_postgres(): 
        print(f"[{datetime.now()}] Exiting tracker as Postgres is not available.")
        exit(1) 

    temp_conn_for_schema = None
    try:
        temp_conn_for_schema = get_db_connection()
        if temp_conn_for_schema:
            run_schema_sql(temp_conn_for_schema)
        else:
            print(f"[{datetime.now()}] Failed to get DB connection for schema setup. Exiting tracker.")
            exit(1) 
    except Exception as schema_err: 
        print(f"[{datetime.now()}] Error during schema run: {schema_err}. Tracker will attempt to continue, but DB might not be correctly set up.")
    finally:
        if temp_conn_for_schema:
            temp_conn_for_schema.close()
    
    run_tracker()