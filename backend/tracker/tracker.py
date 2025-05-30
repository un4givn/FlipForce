print("[TrackerDiag] tracker.py execution started - TOP OF FILE") # You can remove this if you wish
import time
import requests
import psycopg2
import os
from datetime import datetime
from config import get_db_connection # Assuming config.py is in the same directory or accessible

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
    {"category_name": "Misc.", "series_name": "Multi-Sport"}, # Corrected "Misc" to "Misc."
    {"category_name": "Misc.", "series_name": "Pokemon"},   # Corrected "Misc" to "Misc."
]

SLAB_PACK_CATEGORIES_URL = "https://api.arenaclub.com/v2/slab-pack-categories"
ARENA_CLUB_API_BASE_URL = "https://api.arenaclub.com/v2/slab-pack-series/"


def fetch_all_pack_data_from_categories_endpoint():
    """Fetches the complete list of pack categories and series."""
    try:
        print(f"[{datetime.now()}] Fetching all pack categories from {SLAB_PACK_CATEGORIES_URL}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://arenaclub.com/',
            'Origin': 'https://arenaclub.com'
        }
        response = requests.get(SLAB_PACK_CATEGORIES_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now()}] HTTP error fetching all pack categories: {e}. Response: {e.response.text if e.response else 'No response'}")
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching all pack categories data: {e}")
    return None

def fetch_slab_pack(series_id):
    api_url = f"{ARENA_CLUB_API_BASE_URL}{series_id}"
    try:
        print(f"[{datetime.now()}] Fetching detailed data for series: {series_id} from {api_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now()}] HTTP error for series {series_id}: {e}. Response: {e.response.text if e.response else 'No response'}")
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching slab pack data for series {series_id}: {e}")
    return None

def run_schema_sql(conn):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r") as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"[{datetime.now()}] Schema loaded into database.")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to run schema.sql: {e}")
        raise

def store_snapshot_and_update_max(conn, pack_detail_data):
    with conn.cursor() as cur:
        series_id_from_pack = pack_detail_data["id"]
        name = pack_detail_data.get("name", "Unknown")
        
        series_tier = "Unknown" # This is the pack's main category tier (e.g. Diamond, Emerald)
        if pack_detail_data.get("slabPackCategory") and isinstance(pack_detail_data["slabPackCategory"], dict):
            series_tier = pack_detail_data["slabPackCategory"].get("name", "Unknown")
        elif pack_detail_data.get("tier"): # Fallback, though slabPackCategory.name is preferred
            series_tier = pack_detail_data.get("tier", "Unknown")

        cost = pack_detail_data.get("costCents")
        if cost is None and pack_detail_data.get("slabPackCategory"): # Check if cost is in slabPackCategory if not top-level
            cost = pack_detail_data.get("slabPackCategory", {}).get("priceCents", 0)
        else:
            cost = cost if cost is not None else 0 # Default to 0 if still None

        sold_count_api = pack_detail_data.get("packsSold", 0)
        total_count_api = pack_detail_data.get("packsTotal", 0)
        status = "active" if pack_detail_data.get("isActive") else "inactive"

        cur.execute(
            """
            INSERT INTO pack_series_metadata (series_id, name, tier, cost_cents, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (series_id) DO UPDATE SET
                name = EXCLUDED.name,
                tier = EXCLUDED.tier,
                cost_cents = EXCLUDED.cost_cents,
                status = EXCLUDED.status,
                last_seen = NOW();
            """,
            (series_id_from_pack, name, series_tier, cost, status)
        )
        
        cur.execute(
            """
            INSERT INTO pack_snapshots (series_id, packs_sold, packs_total)
            VALUES (%s, %s, %s);
            """,
            (series_id_from_pack, sold_count_api, total_count_api)
        )

        cur.execute("SELECT max_sold FROM pack_max_sold WHERE series_id = %s;", (series_id_from_pack,))
        result = cur.fetchone()
        if result is None:
            cur.execute("INSERT INTO pack_max_sold (series_id, max_sold) VALUES (%s, %s);", (series_id_from_pack, sold_count_api))
        elif isinstance(sold_count_api, int) and result[0] is not None and sold_count_api > result[0]:
            cur.execute(
                """
                UPDATE pack_max_sold
                SET max_sold = %s, last_updated = NOW()
                WHERE series_id = %s;
                """,
                (sold_count_api, series_id_from_pack)
            )
    conn.commit()

def wait_for_postgres(retries=30, delay=2):
    for i in range(retries):
        try:
            conn_pg = get_db_connection()
            if conn_pg:
                conn_pg.close()
            print(f"[{datetime.now()}] Postgres is ready.")
            return
        except psycopg2.OperationalError:
            print(f"[{datetime.now()}] Waiting for Postgres ({i+1}/{retries})...")
            time.sleep(delay)
    raise RuntimeError("Postgres not ready after multiple attempts.")

def compute_newly_sold_cards_and_snapshot(conn, series_id, current_cards_with_tier):
    current_card_ids = set(card["id"] for card in current_cards_with_tier if "id" in card)

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))
        prev_snapshots = cur.fetchall()
        
        column_names = [desc[0] for desc in cur.description] if cur.description else []
        
        prev_card_ids = set()
        prev_card_data_map = {} 

        if column_names:
            for row in prev_snapshots:
                card_dict = dict(zip(column_names, row))
                if "card_id" in card_dict:
                    prev_card_ids.add(card_dict["card_id"]) 
                    prev_card_data_map[card_dict["card_id"]] = card_dict
                else:
                    print(f"[ERROR] 'card_id' not found in columns of pack_card_snapshots. Columns: {column_names} for row: {row}")

        sold_card_ids = prev_card_ids - current_card_ids
        newly_sold_count = len(sold_card_ids)

        enriched_sales = []
        if newly_sold_count > 0:
            for card_id_sold in sold_card_ids:
                c_data = prev_card_data_map.get(card_id_sold, {}) 
                enriched_sales.append((
                    series_id, card_id_sold, c_data.get("tier"), c_data.get("player_name"),
                    c_data.get("overall"), c_data.get("insert_name"), c_data.get("set_number"),
                    c_data.get("set_name"), c_data.get("holo"), c_data.get("rarity"),
                    c_data.get("parallel_number"), c_data.get("parallel_total"),
                    c_data.get("parallel_name"), c_data.get("front_image"), c_data.get("back_image"),
                    c_data.get("slab_kind"), c_data.get("grading_company"), c_data.get("estimated_value_cents")
                ))

            if enriched_sales:
                cur.executemany(
                    """
                    INSERT INTO sold_card_events (
                        series_id, card_id, tier, player_name, overall, insert_name,
                        set_number, set_name, holo, rarity, parallel_number,
                        parallel_total, parallel_name, front_image, back_image,
                        slab_kind, grading_company, estimated_value_cents, sold_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """, enriched_sales
                )

        cur.execute("DELETE FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))

        snapshot_insert_values = []
        if current_cards_with_tier: 
            for card_api_data in current_cards_with_tier:
                if "id" not in card_api_data:
                    print(f"[ERROR] Card data missing 'id': {card_api_data.get('playerName', 'Unknown Player')}")
                    continue 
                snapshot_insert_values.append((
                    series_id, card_api_data["id"], card_api_data.get("tier_name"), card_api_data.get("playerName"),
                    card_api_data.get("overall"), card_api_data.get("insert"), card_api_data.get("setNumber"),
                    card_api_data.get("setName"), card_api_data.get("holo"), card_api_data.get("rarity"),
                    card_api_data.get("parallelNumber"), card_api_data.get("parallelTotal"),
                    card_api_data.get("parallelName"), card_api_data.get("frontSlabPictureUrl"), 
                    card_api_data.get("backSlabPictureUrl"), card_api_data.get("slabKind"),
                    card_api_data.get("gradingCompany"), card_api_data.get("estimatedValueCents")
                ))
            
            if snapshot_insert_values:
                print(f"[DEBUG] Inserting snapshot for series {series_id} with {len(snapshot_insert_values)} cards.")
                cur.executemany(
                    """
                    INSERT INTO pack_card_snapshots (
                        series_id, card_id, tier, player_name, overall, insert_name,
                        set_number, set_name, holo, rarity, parallel_number,
                        parallel_total, parallel_name, front_image, back_image,
                        slab_kind, grading_company, estimated_value_cents
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, snapshot_insert_values
                )
            elif current_cards_with_tier:
                 print(f"[DEBUG] current_cards_with_tier provided for series {series_id}, but no valid cards found to snapshot after filtering.")

        if newly_sold_count > 0:
            cur.execute(
                """
                INSERT INTO pack_sales_tracker (series_id, total_sold, last_checked)
                VALUES (%s, %s, NOW())
                ON CONFLICT (series_id) DO UPDATE
                SET total_sold = pack_sales_tracker.total_sold + EXCLUDED.total_sold,
                    last_checked = NOW();
                """,
                (series_id, newly_sold_count)
            )
    conn.commit() 
    return newly_sold_count

def store_current_pack_total_value(conn, series_id, total_value_cents):
    """
    Stores a snapshot of the total estimated value of all cards currently in the pack series.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pack_total_value_snapshots (series_id, total_estimated_value_cents, snapshot_time)
                VALUES (%s, %s, NOW());
                """,
                (series_id, total_value_cents)
            )
        conn.commit()
        print(f"[{datetime.now()}] Recorded total available pack value for series {series_id}: {total_value_cents} cents.")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR storing total pack value for series {series_id}: {e}")
        if conn: # Attempt to rollback if connection exists
            try:
                conn.rollback()
            except Exception as rb_e:
                print(f"[{datetime.now()}] ERROR during rollback for total pack value: {rb_e}")

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
                                        "series_name_log": series_in_category.get("name")
                                    })
                                    print(f"[{datetime.now()}] Found Series ID: {found_series_id_for_target} for target: {target_pack['category_name']} - {target_pack['series_name']}")
                                break 
                        if found_series_id_for_target:
                            break 
                
                if not found_series_id_for_target:
                    print(f"[{datetime.now()}] WARN: Could not find current series_id for target: {target_pack['category_name']} - {target_pack['series_name']}")
            
            if not discovered_series_to_process:
                print(f"[{datetime.now()}] No series IDs found for targeted packs in this cycle. Waiting 5 minutes...")
                time.sleep(300) 
                continue

            for series_info_to_process in discovered_series_to_process:
                current_series_id_from_discovery = series_info_to_process["id"]
                
                detailed_pack_data = fetch_slab_pack(current_series_id_from_discovery) 

                if detailed_pack_data:
                    api_series_id_in_detail = detailed_pack_data.get("id")
                    if not api_series_id_in_detail:
                        print(f"[{datetime.now()}] ERROR: 'id' not found in detailed_pack_data for discovered ID {current_series_id_from_discovery}. Skipping.")
                        continue
                    
                    if api_series_id_in_detail != current_series_id_from_discovery:
                         print(f"[{datetime.now()}] WARN: ID mismatch! Discovered: {current_series_id_from_discovery}, Detail Endpoint: {api_series_id_in_detail} for {series_info_to_process['series_name_log']}. Using ID from detail endpoint: {api_series_id_in_detail}.")
                    
                    authoritative_series_id = api_series_id_in_detail

                    all_cards_for_this_series_with_tier = []
                    slab_pack_tiers = detailed_pack_data.get("slabPackTiers")

                    if isinstance(slab_pack_tiers, list): 
                        for tier_info_item in slab_pack_tiers:
                            if isinstance(tier_info_item, dict):
                                tier_name_from_slab = tier_info_item.get("name", "Unknown Tier")
                                cards_in_tier_list = tier_info_item.get("cards")
                                if isinstance(cards_in_tier_list, list):
                                    for card_data_item in cards_in_tier_list:
                                        if isinstance(card_data_item, dict):
                                            card_api_data_with_tier = card_data_item.copy()
                                            card_api_data_with_tier["tier_name"] = tier_name_from_slab
                                            all_cards_for_this_series_with_tier.append(card_api_data_with_tier)
                                        else:
                                            print(f"[{datetime.now()}] Card data in tier '{tier_name_from_slab}' for series {authoritative_series_id} is not a dict: {card_data_item}")
                                else:
                                     print(f"[{datetime.now()}] 'cards' key in tier_info for series {authoritative_series_id}, tier '{tier_name_from_slab}', is not a list: {cards_in_tier_list}")
                            else:
                                print(f"[{datetime.now()}] Tier data item for series {authoritative_series_id} is not a dict: {tier_info_item}")
                    else:
                        print(f"[{datetime.now()}] WARN: 'slabPackTiers' not found or not a list in detailed_pack_data for series {authoritative_series_id}. Card-specific tiers (Grail, Chase) cannot be extracted.")
                    
                    # --- Calculate and store current total value of available cards ---
                    current_total_available_value_cents = 0
                    for card_data in all_cards_for_this_series_with_tier:
                        value = card_data.get("estimatedValueCents")
                        if isinstance(value, (int, float)): # Check if it's a number
                            current_total_available_value_cents += value
                        elif value is not None: # Log if it exists but isn't a number (e.g. string)
                            print(f"[{datetime.now()}] WARN: 'estimatedValueCents' for a card in series {authoritative_series_id} is not a number: {value}. Skipping this value.")
                        # If value is None, it's correctly ignored (adds 0 implicitly if we started sum with 0)
                    
                    if db_conn:
                        store_current_pack_total_value(db_conn, authoritative_series_id, current_total_available_value_cents)
                    # --- End total value calculation and storage ---

                    store_snapshot_and_update_max(db_conn, detailed_pack_data) # type: ignore
                    sold_count = compute_newly_sold_cards_and_snapshot(db_conn, authoritative_series_id, all_cards_for_this_series_with_tier)
                    
                    pack_name_log = detailed_pack_data.get('name', 'Unknown Name')
                    total_value_log = current_total_available_value_cents / 100.0 if isinstance(current_total_available_value_cents, (int, float)) else 'N/A'
                    if isinstance(total_value_log, float): total_value_log = f"{total_value_log:.2f}"

                    print(f"[{datetime.now()}] Pack processed: {pack_name_log} (Series ID: {authoritative_series_id}) | Cards in API: {len(all_cards_for_this_series_with_tier)} | Sold this run: {sold_count} | Total Value Now: ${total_value_log}")
                else:
                    print(f"[{datetime.now()}] No detailed data fetched for series (Discovered ID: {current_series_id_from_discovery}). Skipping.")
                time.sleep(2) 
            
            print(f"[{datetime.now()}] Completed processing all targeted series for this iteration. Waiting 15 minutes before next cycle...")
            time.sleep(2) # 15 minutes
            
    except KeyboardInterrupt:
        print(f"[{datetime.now()}] Tracker stopped by user.")
    except Exception as e:
        print(f"[{datetime.now()}] UNEXPECTED ERROR in run_tracker: {e}")
        import traceback
        traceback.print_exc()
        if db_conn:
            try:
                db_conn.close() # Close connection on error
            except Exception as db_close_e:
                print(f"[{datetime.now()}] Error closing DB connection during exception handling: {db_close_e}")
            db_conn = None # Set to None after closing or if close fails
            print(f"[{datetime.now()}] DB connection closed due to error. Tracker will attempt to re-establish on next cycle if error is recoverable, or exit if loop is broken.")
            time.sleep(60) # Wait a bit before potential restart if in a loop not shown
    finally:
        if db_conn: # Ensure connection is closed if loop finishes or on normal exit
            try:
                db_conn.close()
                print(f"[{datetime.now()}] Database connection closed normally.")
            except Exception as e:
                print(f"[{datetime.now()}] Error closing database connection in finally block: {e}")

if __name__ == "__main__":
    wait_for_postgres()
    temp_conn_for_schema = None
    try:
        temp_conn_for_schema = get_db_connection()
        if temp_conn_for_schema:
            run_schema_sql(temp_conn_for_schema) # This will execute the updated schema.sql
        else:
            print(f"[{datetime.now()}] Failed to get DB connection for schema setup. Exiting tracker.")
            exit(1) 
    except Exception as schema_err:
        print(f"[{datetime.now()}] Error during schema run: {schema_err}. Continuing to tracker, but DB might not be set up correctly.")
    finally:
        if temp_conn_for_schema:
            temp_conn_for_schema.close()
            
    run_tracker()