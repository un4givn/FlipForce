import requests
import json
import csv

SEARCH_URL = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc/public.sci.cards.search"
SALES_URL = "https://d1ekdvyhrdz9i5.cloudfront.net/trpc/public.sci.cards.getCompletedSales"
HEADERS = {
    "User-Agent": "scimobile/201 CFNetwork/3852.100.1 Darwin/25.0.0",
    "Accept": "*/*",
    "Content-Type": "application/json"
}

def search_cards(query_text: str, offset: int = 0):
    payload = {
        "filters": {
            "indexId": "ts_1749632447409",
            "searchQueryText": query_text
        },
        "offset": offset
    }

    params = {
        "input": json.dumps(payload)
    }

    response = requests.get(SEARCH_URL, headers=HEADERS, params=params)
    try:
        results = response.json()
        cards = results["result"]["data"]["items"]

        extracted = []
        for card in cards:
            cid = card.get("collectible_id")
            player = card.get("player", "Unknown")
            variation = card.get("variation", "Base")
            year = card.get("set_year", "")
            set_name = card.get("set_name", "")
            card_number = card.get("card_number", "?")
            is_rc = " (RC)" if card.get("is_rc") else ""
            title = f"{year} {set_name} #{card_number} {player} - {variation}{is_rc}"
            extracted.append({
                "collectible_id": cid,
                "title": title,
                "image_url": card.get("image_url", "")
            })

        # Export card info
        with open("cards_output.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["collectible_id", "title", "image_url"])
            writer.writeheader()
            writer.writerows(extracted)

        print(f"✅ Exported {len(extracted)} cards to cards_output.csv")
        return [int(c["collectible_id"]) for c in extracted if c["collectible_id"]]

    except Exception as e:
        print("❌ Failed to parse search response:", e)
        print("Raw search response:", response.text)
        return []

def fetch_sales(collectible_ids):
    input_obj = {
        "filters": {
            "collectibleIds": collectible_ids
        }
    }

    params = {
        "input": json.dumps(input_obj)
    }

    response = requests.get(SALES_URL, headers=HEADERS, params=params)
    try:
        results = response.json()
        sales = results["result"]["data"]
        with open("sales_output.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["collectible_id", "price", "platform", "timestamp", "buyer_fee", "seller_fee"])
            writer.writeheader()
            for sale in sales:
                writer.writerow({
                    "collectible_id": sale.get("collectibleId"),
                    "price": sale.get("salePrice"),
                    "platform": sale.get("marketplace"),
                    "timestamp": sale.get("saleDate"),
                    "buyer_fee": None,
                    "seller_fee": None,
                })

        print(f"✅ Exported {len(sales)} sales to sales_output.csv")
    except Exception as e:
        print("❌ Failed to parse sales response:", e)
        print("Raw sales response:", response.text)

# Run both steps
if __name__ == "__main__":
    ids = search_cards("Jayden Daniels prizm silver")
    if ids:
        fetch_sales(ids)
