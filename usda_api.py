import os
import requests
from dotenv import load_dotenv

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")

BASE_URL = "https://api.nal.usda.gov/fdc/v1"


def search_food(query, page_size=5):
    if not USDA_API_KEY:
        raise RuntimeError(
            "USDA_API_KEY is not configured"
        )

    response = requests.get(
        f"{BASE_URL}/foods/search",
        params={
            "api_key": USDA_API_KEY,
            "query": query,
            "pageSize": page_size
        },
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return data.get("foods", [])


def get_nutrition_per_100g(fdc_id):
    food = get_food_details(fdc_id)

    nutrition = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0
    }

    for nutrient in food.get("foodNutrients", []):

        # USDA can return nutrients in different structures
        nutrient_info = nutrient.get("nutrient", {})

        name = nutrient_info.get("name")
        amount = nutrient.get("amount")

        if amount is None:
            continue

        if not name:
            continue

        name_lower = name.lower()

        if (
            name_lower == "energy"
            or "energy" in name_lower
        ):
            nutrition["calories"] = float(amount)

        elif name_lower == "protein":
            nutrition["protein"] = float(amount)

        elif (
            "carbohydrate" in name_lower
            and "difference" in name_lower
        ):
            nutrition["carbs"] = float(amount)

        elif (
            name_lower == "total lipid (fat)"
            or name_lower == "total fat"
            or "total lipid" in name_lower
        ):
            nutrition["fat"] = float(amount)

    return nutrition


def calculate_nutrition(fdc_id, quantity_grams):
    nutrition = get_nutrition_per_100g(fdc_id)

    multiplier = quantity_grams / 100

    return {
        "calories": round(
            nutrition["calories"] * multiplier,
            2
        ),
        "protein": round(
            nutrition["protein"] * multiplier,
            2
        ),
        "carbs": round(
            nutrition["carbs"] * multiplier,
            2
        ),
        "fat": round(
            nutrition["fat"] * multiplier,
            2
        )
    }

def get_food_details(fdc_id):
    if not USDA_API_KEY:
        raise RuntimeError(
            "USDA_API_KEY is not configured"
        )

    response = requests.get(
        f"{BASE_URL}/food/{fdc_id}",
        params={
            "api_key": USDA_API_KEY
        },
        timeout=10
    )

    response.raise_for_status()

    return response.json()