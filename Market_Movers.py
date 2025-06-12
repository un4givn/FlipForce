import requests
import json
from datetime import datetime

# Disable SSL warnings, which can occur on some environments
try:
    requests.packages.urllib3.disable_warnings()
except:
    pass

# --- API Configuration ---
SETTINGS_URL = "https://scour-index-prod.s3.us-east-2.amazonaws.com/settings_v2.json"
API_BASE_URL = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc"
HEADERS = {"User-Agent": "scimobile/201 CFNetwork/3852.100.1 Darwin/25.0.0"}

def get_live_index_id(session):
    """Fetches the latest search indexId from the settings file."""
    print("Fetching latest settings...")
    try:
        response = session.get(SETTINGS_URL, headers=HEADERS, verify=False)
        response.raise_for_status()
        settings = response.json()
        index_id = settings.get("card", {}).get("indexId")
        if index_id:
            print(f"✅ Success! Using live indexId: {index_id}")
            return index_id
    except Exception as e:
        print(f"❌ Could not fetch live settings: {e}")
    print("Using fallback indexId.")
    return "ts_1749632447409"

def search_for_collectibles(session, index_id, query):
    """
    Searches for parent collectibles and returns the list.
    Each result contains nested variations for each grade.
    """
    print(f"\nSearching for collectibles matching: '{query}'...")
    url = f"{API_BASE_URL}/public.sci.cards.search"
    payload = {"filters": {"indexId": index_id, "searchQueryText": query}, "offset": 0}
    params = {"input": json.dumps(payload)}
    try:
        response = session.get(url, headers=HEADERS, params=params, verify=False)
        response.raise_for_status()
        collectibles = response.json()["result"]["data"]["items"]
        if not collectibles:
            print("No results found.")
            return None
        return collectibles
    except Exception as e:
        print(f"❌ Search failed: {e}")
    return None

def get_completed_sales(session, specific_card_id):
    """Fetches completed sales using a specific, grade-level collectibleId."""
    print(f"\nFetching comps for specific ID: {specific_card_id}...")
    url = f"{API_BASE_URL}/public.sci.cards.getCompletedSales"
    payload = {"filters": {"collectibleIds": [specific_card_id]}}
    params = {"input": json.dumps(payload)}
    try:
        response = session.get(url, headers=HEADERS, params=params, verify=False)
        response.raise_for_status()
        sales = response.json()["result"]["data"]
        if not sales:
            print("No recent sales data found for this specific card variation.")
            return

        print("\n--- Recent Sales (Comps) ---")
        for sale in sales:
            title = sale.get("saleTitle", "N/A")
            price = sale.get("salePrice")
            sale_date_str = sale.get("saleDate", "")
            sale_date = datetime.fromisoformat(sale_date_str.replace("Z", "+00:00")) if sale_date_str else None
            
            print(f"  - Title: {title}")
            print(f"    Price: ${price:,.2f}")
            print(f"    Date: {sale_date.strftime('%Y-%m-%d') if sale_date else 'N/A'}")
            print("-" * 15)

    except Exception as e:
        print(f"❌ Comps fetch failed: {e}")

if __name__ == "__main__":
    with requests.Session() as session:
        live_index_id = get_live_index_id(session)
        search_query = input("\nEnter the card you want to comp: ")

        if search_query:
            # Step 1: Search for the parent collectibles
            collectibles = search_for_collectibles(session, live_index_id, search_query)

            if collectibles:
                print("\n--- Search Results ---")
                for i, item in enumerate(collectibles):
                    title = f"{item.get('set_year', '')} {item.get('set_name', '')} #{item.get('card_number', '?')} {item.get('player', 'Unknown')} - {item.get('variation', 'Base')}"
                    print(f"  {i + 1}. {title}")
                
                try:
                    # Step 2: User selects a parent collectible
                    parent_choice = int(input("\nSelect the card you are interested in: ")) - 1
                    if 0 <= parent_choice < len(collectibles):
                        selected_collectible = collectibles[parent_choice]
                        
                        # CORRECTED: The nested list is under the 'grades' key
                        variations = selected_collectible.get("grades", [])
                        
                        if not variations:
                            print("No graded or raw variations found for this card.")
                        else:
                            print("\nPlease select the specific variation:")
                            for i, var in enumerate(variations):
                                # CORRECTED: The name is under the 'grade_name' key
                                print(f"  {i + 1}. {var.get('grade_name')}")
                            
                            # Step 3: User selects the specific grade/variation
                            var_choice = int(input("\nEnter selection number: ")) - 1
                            if 0 <= var_choice < len(variations):
                                # CORRECTED: The specific ID is under the 'card_id' key
                                specific_id = variations[var_choice].get("card_id")
                                
                                # Step 4: Fetch sales using the final, specific ID
                                get_completed_sales(session, int(specific_id))
                            else:
                                print("Invalid variation selection.")
                    else:
                        print("Invalid card selection.")
                except (ValueError, IndexError):
                    print("Invalid input.")