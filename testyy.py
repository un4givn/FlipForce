import requests
import json
from datetime import datetime

# URLs and Headers
SETTINGS_URL       = "https://scour-index-prod.s3.us-east-2.amazonaws.com/settings_v2.json"
SEARCH_URL         = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc/public.sci.cards.search"
SALES_URL          = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc/public.sci.cards.getCompletedSales"
FILTER_OPTIONS_URL = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc/public.sci.cards.getFilterOptions"

HEADERS = {
    "User-Agent":   "scimobile/201 CFNetwork/3852.100.1 Darwin/25.0.0",
    "Accept":       "*/*",
    "Content-Type": "application/json"
}

def get_latest_index_id():
    print("Fetching latest settings to get current indexId...")
    try:
        r = requests.get(SETTINGS_URL, headers=HEADERS)
        r.raise_for_status()
        idx = r.json().get("card", {}).get("indexId")
        print(f"✅ Using live indexId: {idx}")
        return idx
    except:
        fallback = "ts_1749632447409"
        print(f"⚠️ Could not fetch live indexId — falling back to {fallback}")
        return fallback

def get_filter_options(index_id, key, *, search_query="*", sort_direction=None, limit=None):
    payload = {
        "filters": {"indexId": index_id, "searchQueryText": search_query},
        "filterKey": key
    }
    if sort_direction: payload["sortDirection"] = sort_direction
    if limit:          payload["limit"] = limit

    r = requests.get(FILTER_OPTIONS_URL, headers=HEADERS, params={"input": json.dumps(payload)})
    r.raise_for_status()
    raw = r.json()["result"]["data"]

    # Normalize dict forms into list of {value,count}
    if isinstance(raw, dict):
        if "options" in raw:
            opts = raw["options"]
            cnts = raw.get("counts", [])
            return [
                {"value": v, "count": cnts[i] if i < len(cnts) else None}
                for i, v in enumerate(opts)
            ]
        return [{"value": k, "count": raw[k]} for k in raw]
    return raw  # already list

def search_for_card(index_id, query, *, year=None, grade=None):
    print(f"\n🔍 Searching for '{query}'" +
          (f", year={year}" if year else "") +
          (f", grade={grade}" if grade else "") + "...\n")
    filters = {"indexId": index_id, "searchQueryText": query}
    if year:  filters["setYears"] = [year]
    if grade: filters["grades"]   = [grade]  # server honors this in search

    payload = {"filters": filters, "offset": 0}
    r = requests.get(SEARCH_URL, headers=HEADERS, params={"input": json.dumps(payload)})
    r.raise_for_status()
    return r.json()["result"]["data"]["items"]

def get_card_comps(collectible_id):
    print(f"\n📊 Fetching completed sales for ID {collectible_id} ...")
    payload = {"filters": {"collectibleIds": [int(collectible_id)]}}
    r = requests.get(SALES_URL, headers=HEADERS, params={"input": json.dumps(payload)})
    r.raise_for_status()

    sales = r.json()["result"]["data"] or []
    if not sales:
        print("⚠️  No completed sales found for that card.")
        return

    print(f"\n--- {len(sales)} Completed Sales ---")
    for s in sales:
        dt = datetime.fromisoformat(s["saleDate"].replace("Z", "+00:00"))
        print(f"• ${s['salePrice']:,.2f} on {dt.date()} [{s['listingType']}]")

if __name__ == "__main__":
    idx = get_latest_index_id()

    # 1) Show top‐10 years
    years = get_filter_options(idx, "setYears", sort_direction="desc")
    print("\nAvailable release years:")
    for y in years[:10]:
        label = f"{y['value']} ({y['count']} cards)" if y["count"] is not None else y["value"]
        print("  ", label)
    year = input("\nEnter year to filter by (blank = all): ").strip() or None

    # 2) Ask for grade
    grade_str = input("Enter a GRADE to filter search by (e.g. 10 for PSA 10; blank = all): ").strip()
    grade = int(grade_str) if grade_str.isdigit() else None

    # 3) Ask for the card name
    term = input("\nEnter the card name to search: ").strip()
    if not term:
        print("No card name entered. Exiting."); exit()

    # 4) Perform the search with optional year+grade
    items = search_for_card(idx, term + "*", year=year, grade=grade)
    if not items:
        print("⚠️  No matching cards found."); exit()

    # 5) Display results
    print("\n--- Search Results ---")
    for i, c in enumerate(items, 1):
        title = f"{c['set_year']} {c['set_name']} #{c['card_number']} {c['player']}"
        rc    = " (RC)" if c.get("is_rc") else ""
        print(f"{i}. {title}{rc} — ID {c['collectible_id']}")

    # 6) Let user pick
    choice = input(f"\nChoose a result number (1–{len(items)}): ").strip()
    try:
        idx_choice = int(choice) - 1
        if idx_choice not in range(len(items)):
            raise ValueError
        chosen_id = items[idx_choice]["collectible_id"]
    except:
        print("Invalid choice. Exiting."); exit()

    # 7) Fetch comps for that collectible_id
    get_card_comps(chosen_id)
