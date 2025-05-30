print("[TrackerDiag] tracker.py execution started - TOP OF FILE") # You can remove this if you wish
import time
import requests
import psycopg2
import os
from datetime import datetime
from config import get_db_connection

print("[Tracker] ✅ tracker.py has started.")

# 👇 Replace these with your real slab-pack seriesIds
# Example:
SERIES_IDS = [
     "fa054346-adb1-409f-8fef-3fccc1c0280d", #DMS
     "21d794e4-ed1e-4a9b-8758-899de0e53eaa", #DP
     "c5f7a920-790c-4396-b0e2-1c8aa7050f9f", #EBASKET
     "21d794e4-ed1e-4a9b-8758-899de0e53eaa", #EBASE
     "9cd737fa-34c6-494e-8f73-c13431236cf8", #EFOOT
     "cad71867-be75-49b3-ad34-9abc1325a743", #EPOKE
     "c688501b-835e-4ca5-bf81-540e234d8e90", #RBASKET
     "775a4e3c-7142-46e1-ac09-03094ab54bcb", #RBASE
     "0d63f805-4832-4f2d-8b84-6e8661c6c1b9", #RFOOT
     "197f94b9-4f13-41ba-bd82-7013b1afa572", #RPOKE
     "dffa3ffd-73e6-4720-a093-0a6c2780b113", #GBASKET
     "bd6f445e-f8b6-403d-af71-acef2a85c0a2", #GBASE
     "3e8fa8c8-9023-41de-9052-67dc45bba5fb", #GFOOT
     "c43ab013-f7d9-4930-b2fd-f06eb8191de3", #GPOKE
     "f4ffc460-30ae-403e-9229-b377e88e9d64", #SBASKET
     "b4cc985a-19d9-4a70-a63e-f75be7041d17", #SBASE
     "3301718b-d863-4026-b022-6c0b6edcfa92", #SFOOT
     "51bb9200-bf67-4900-bdd3-705cb18b58fd", #SPOKE
     "c04d5d54-23b4-4484-ba1c-1dc307b88c84", #MISC
     "cb14cc57-f20d-47e9-8fde-03467aad2034", #MISCPOKE
 ]

ARENA_CLUB_API_BASE_URL = "https://api.arenaclub.com/v2/slab-pack-series/"

def fetch_slab_pack(series_id): # Modified to accept series_id
    api_url = f"{ARENA_CLUB_API_BASE_URL}{series_id}" # Construct URL dynamically
    try:
        print(f"[{datetime.now()}] Fetching data for series: {series_id} from {api_url}")
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now()}] HTTP error for series {series_id}: {e}")
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

def store_snapshot_and_update_max(conn, pack):
    # This function already uses pack["id"] which is the series_id,
    # so it inherently handles different series correctly.
    with conn.cursor() as cur:
        series_id_from_pack = pack["id"] # Use 'id' from pack data as series_id
        name = pack.get("name", "Unknown")
        tier = pack.get("tier", "Unknown") # This might need to be derived if not top-level
        cost = pack.get("costCents") 
        if cost is None and pack.get("slabPackCategory"): # Try to get cost from slabPackCategory if top-level is missing
            cost = pack.get("slabPackCategory", {}).get("priceCents", 0)
        else:
            cost = cost if cost is not None else 0


        sold = pack.get("packsSold", 0) # This might not be available directly, check API response
        total = pack.get("packsTotal", 0) # This might not be available directly, check API response
        status = "active" if pack.get("isActive") else "inactive"


        # 1. Insert snapshot (pack_snapshots is about overall pack numbers)
        cur.execute(
            """
            INSERT INTO pack_snapshots (series_id, packs_sold, packs_total)
            VALUES (%s, %s, %s);
            """,
            (series_id_from_pack, sold, total)
        )

        # 2. Update metadata
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
            (series_id_from_pack, name, tier, cost, status)
        )

        # 3. Update max_sold
        cur.execute("SELECT max_sold FROM pack_max_sold WHERE series_id = %s;", (series_id_from_pack,))
        result = cur.fetchone()
        if result is None:
            cur.execute("INSERT INTO pack_max_sold (series_id, max_sold) VALUES (%s, %s);", (series_id_from_pack, sold))
        elif sold > result[0]:
            cur.execute(
                """
                UPDATE pack_max_sold
                SET max_sold = %s, last_updated = NOW()
                WHERE series_id = %s;
                """,
                (sold, series_id_from_pack)
            )
    conn.commit()

def wait_for_postgres(retries=30, delay=2):
    for i in range(retries):
        try:
            conn = get_db_connection()
            conn.close() # type: ignore
            print(f"[{datetime.now()}] Postgres is ready.")
            return
        except psycopg2.OperationalError:
            print(f"[{datetime.now()}] Waiting for Postgres ({i+1}/{retries})...")
            time.sleep(delay)
    raise RuntimeError("Postgres not ready after multiple attempts.")

def compute_newly_sold_cards_and_snapshot(conn, series_id, current_cards):
    current_card_ids = set(card["id"] for card in current_cards) # Ensure card["id"] exists

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))
        prev_snapshots = cur.fetchall()
        
        column_names = []
        if cur.description: # Check if cursor has a description (i.e., query returned columns)
            column_names = [desc[0] for desc in cur.description]
        
        prev_card_ids = set()
        prev_card_data_map = {} 

        if column_names: # Proceed only if we have column names (meaning prev_snapshots might have data)
            for row in prev_snapshots:
                card_dict = dict(zip(column_names, row))
                if "card_id" in card_dict: # Ensure 'card_id' column exists
                    prev_card_ids.add(card_dict["card_id"]) 
                    prev_card_data_map[card_dict["card_id"]] = card_dict
                else:
                    print(f"[ERROR] 'card_id' not found in columns of pack_card_snapshots for a row. Columns: {column_names}")


        sold_card_ids = prev_card_ids - current_card_ids
        newly_sold = len(sold_card_ids)

        enriched_sales = []
        if newly_sold > 0:
            for card_id_sold in sold_card_ids:
                c_data = prev_card_data_map.get(card_id_sold, {}) 
                enriched_sales.append((
                    series_id,
                    card_id_sold,
                    c_data.get("player_name"),
                    c_data.get("overall"),
                    c_data.get("insert_name"),
                    c_data.get("set_number"),
                    c_data.get("set_name"),
                    c_data.get("holo"),
                    c_data.get("rarity"),
                    c_data.get("parallel_number"),
                    c_data.get("parallel_total"),
                    c_data.get("parallel_name"),
                    c_data.get("front_image"),
                    c_data.get("back_image"),
                    c_data.get("slab_kind"),
                    c_data.get("grading_company"),
                    c_data.get("estimated_value_cents")
                ))

            if enriched_sales:
                cur.executemany(
                    """
                    INSERT INTO sold_card_events (
                        series_id, card_id, player_name, overall, insert_name,
                        set_number, set_name, holo, rarity, parallel_number,
                        parallel_total, parallel_name, front_image, back_image,
                        slab_kind, grading_company, estimated_value_cents, sold_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    enriched_sales
                )

        cur.execute("DELETE FROM pack_card_snapshots WHERE series_id = %s;", (series_id,))

        snapshot_insert_values = []
        if current_cards: 
            for card_api_data in current_cards:
                # Ensure 'id' key exists in card_api_data, critical for primary key
                if "id" not in card_api_data:
                    print(f"[ERROR] Card data missing 'id': {card_api_data.get('playerName', 'Unknown Player')}")
                    continue 

                snapshot_insert_values.append((
                    series_id,
                    card_api_data["id"], 
                    card_api_data.get("playerName"),
                    card_api_data.get("overall"),
                    card_api_data.get("insert"), # Key from API, table has 'insert_name'. Ensure this is intended.
                    card_api_data.get("setNumber"),
                    card_api_data.get("setName"),
                    card_api_data.get("holo"),
                    card_api_data.get("rarity"),
                    card_api_data.get("parallelNumber"),
                    card_api_data.get("parallelTotal"),
                    card_api_data.get("parallelName"),
                    card_api_data.get("frontSlabPictureUrl"), 
                    card_api_data.get("backSlabPictureUrl"),  
                    card_api_data.get("slabKind"),
                    card_api_data.get("gradingCompany"),
                    card_api_data.get("estimatedValueCents")
                ))
            
            if snapshot_insert_values: # Only print and execute if there are values to insert
                print(f"[DEBUG] Inserting snapshot for series {series_id} with {len(snapshot_insert_values)} cards.")
                cur.executemany(
                    """
                    INSERT INTO pack_card_snapshots (
                        series_id, card_id, player_name, overall, insert_name,
                        set_number, set_name, holo, rarity, parallel_number,
                        parallel_total, parallel_name, front_image, back_image,
                        slab_kind, grading_company, estimated_value_cents
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    snapshot_insert_values
                )
            elif current_cards: # current_cards was not empty, but snapshot_insert_values is (e.g. all cards missing 'id')
                 print(f"[DEBUG] current_cards provided for series {series_id}, but no valid cards found to snapshot after filtering.")
            # else: current_cards was empty, so nothing to insert or log about it here.

        if newly_sold > 0:
            cur.execute(
                """
                INSERT INTO pack_sales_tracker (series_id, total_sold, last_checked)
                VALUES (%s, %s, NOW())
                ON CONFLICT (series_id) DO UPDATE
                SET total_sold = pack_sales_tracker.total_sold + EXCLUDED.total_sold,
                    last_checked = NOW();
                """,
                (series_id, newly_sold)
            )
    conn.commit() 
    return newly_sold
    
def run_tracker():
    print(f"[{datetime.now()}] FlipForce tracker started for multiple series.")
    conn = get_db_connection()
    try:
        while True:
            for current_series_id_from_loop in SERIES_IDS: # Renamed to avoid confusion with id from pack_data
                pack_data = fetch_slab_pack(current_series_id_from_loop)
                if pack_data:
                    all_cards_for_this_series = []
                    slab_pack_tiers = pack_data.get("slabPackTiers") 

                    if isinstance(slab_pack_tiers, list): 
                        for tier in slab_pack_tiers:
                            # Ensure tier is a dictionary and 'cards' is a list within the tier
                            if isinstance(tier, dict) and isinstance(tier.get("cards"), list):
                                all_cards_for_this_series.extend(tier.get("cards", []))
                            elif tier is not None: # If tier is not None but not structured as expected
                                print(f"[{datetime.now()}] Tier data for series {current_series_id_from_loop} is not a dict or 'cards' key is not a list: {tier}")

                    series_id_from_pack_data = pack_data.get("id") # This is the true series_id for this data
                    
                    if not series_id_from_pack_data:
                        print(f"[{datetime.now()}] ERROR: 'id' (series_id) not found in pack_data for fetched URL using {current_series_id_from_loop}. Skipping database operations for this entry.")
                        print(f"Pack data keys: {pack_data.keys() if isinstance(pack_data, dict) else 'Not a dict'}")
                        continue 

                    # Ensure compute_newly_sold_cards_and_snapshot uses the series_id from the pack_data
                    sold = compute_newly_sold_cards_and_snapshot(conn, series_id_from_pack_data, all_cards_for_this_series)
                    
                    print(f"[{datetime.now()}] Pack fetched: {pack_data.get('name', 'Unknown Name')} (Series ID from API: {series_id_from_pack_data}, Loop ID: {current_series_id_from_loop}) | Cards in API: {len(all_cards_for_this_series)} | Sold this run: {sold}")
                    store_snapshot_and_update_max(conn, pack_data) # type: ignore
                else:
                    print(f"[{datetime.now()}] No data fetched for series (Loop ID: {current_series_id_from_loop}). Skipping store.")
                time.sleep(1) 
            
            print(f"[{datetime.now()}] Completed fetching all series for this iteration. Waiting before next cycle...")
            time.sleep(1) 
    except KeyboardInterrupt:
        print("Tracker stopped.")
    except Exception as e:
        print(f"[{datetime.now()}] UNEXPECTED ERROR in run_tracker: {e}") # Catchall for other unexpected errors
        # Potentially add a longer sleep here or re-initialize connection if it's a DB error
        if conn:
            try:
                conn.close() # type: ignore
            except Exception as db_close_e:
                print(f"Error closing DB connection during exception handling: {db_close_e}")
            conn = None # Reset conn
            time.sleep(60) # Wait a bit before trying to restart loop / get new connection
            # Re-establish connection if desired for robustness, or let the script exit/restart via Docker
            print("Attempting to re-establish DB connection and continue...")
            conn = get_db_connection()
            if not conn:
                print("Failed to re-establish DB connection. Exiting loop.")
                raise # Or break
    finally:
        if conn: 
            conn.close() # type: ignore
            print("Database connection closed.")

if __name__ == "__main__":
    wait_for_postgres()
    temp_conn_for_schema = get_db_connection()
    if temp_conn_for_schema:
        try:
            run_schema_sql(temp_conn_for_schema) # type: ignore
        except Exception as schema_err:
            print(f"Error during schema run, but continuing to tracker: {schema_err}")
            # Decide if this error should prevent tracker from starting
        finally:
            temp_conn_for_schema.close() # type: ignore
    else:
        print("Failed to get DB connection for schema setup. Exiting tracker.")
        exit(1) 
        
    run_tracker()