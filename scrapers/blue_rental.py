"""
Blue Car Rental (your own fleet) — included in the matrix so you can
see your own prices alongside competitors at a glance.

Update the price ranges below to match your actual published rates.
When live booking data is available, implement scrape_rates() to pull
real-time prices from your own system instead.
"""

from .base import BaseScraper


class BlueCarRentalScraper(BaseScraper):
    competitor_name = "Blue Car Rental"
    base_url = "https://www.bluecarrental.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",              "price_range": (7500,  7500)},
            {"model": "Kia Rio",                  "price_range": (8000,  8000)},
            {"model": "Toyota Yaris",             "price_range": (9000,  9000)},
            {"model": "Kia Ceed",                 "price_range": (10000, 10000)},
            {"model": "Opel Corsa Electric",      "price_range": (10000, 10000)},
            {"model": "Tesla Model 3",            "price_range": (11000, 11000)},
            {"model": "BYD Dolphin",              "price_range": (9500,  9500)},
            {"model": "Kia EV3",                  "price_range": (10500, 10500)},
            {"model": "Smart #5",                 "price_range": (12000, 12000)},
        ],
        "Compact": [
            {"model": "Kia Stonic",            "price_range": (11000, 11000)},
            {"model": "Kia XCeed",             "price_range": (12000, 12000)},
            {"model": "Kia Ceed Sportswagon",  "price_range": (11500, 11500)},
            {"model": "Dacia Jogger",          "price_range": (10500, 10500)},
        ],
        "SUV": [
            {"model": "Dacia Duster",    "price_range": (14500, 14500)},
            {"model": "Dacia Bigster",   "price_range": (16000, 16000)},
            {"model": "Suzuki Vitara",   "price_range": (15000, 15000)},
            {"model": "Suzuki Jimny",    "price_range": (14000, 14000)},
            {"model": "Jeep Renegade",   "price_range": (16500, 16500)},
            {"model": "Hyundai Tucson",  "price_range": (17000, 17000)},
            {"model": "Kia Sportage",    "price_range": (17500, 17500)},
            {"model": "Toyota RAV4",     "price_range": (19000, 19000)},
            {"model": "Tesla Model Y",   "price_range": (22000, 22000)},
            {"model": "Kia EV6",         "price_range": (21000, 21000)},
            {"model": "MG ZS",           "price_range": (14000, 14000)},
        ],
        "4x4": [
            {"model": "Kia Sorento",               "price_range": (22000, 22000)},
            {"model": "Nissan X-Trail",            "price_range": (22000, 22000)},
            {"model": "Hyundai Santa Fe",          "price_range": (24000, 24000)},
            {"model": "Toyota Land Cruiser 150",   "price_range": (27000, 27000)},
            {"model": "Toyota Land Cruiser 250",   "price_range": (32000, 32000)},
            {"model": "Land Rover Discovery Sport","price_range": (25000, 25000)},
            {"model": "Land Rover Discovery",      "price_range": (30000, 30000)},
            {"model": "Land Rover Defender",       "price_range": (33000, 33000)},
            {"model": "Jeep Wrangler",             "price_range": (29000, 29000)},
            {"model": "Toyota Highlander",         "price_range": (26000, 26000)},
        ],
        "Minivan": [
            {"model": "Renault Trafic",    "price_range": (20000, 20000)},
            {"model": "Toyota Proace",     "price_range": (23000, 23000)},
            {"model": "Mercedes Sprinter", "price_range": (30000, 30000)},
        ],
    }

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        TODO: Connect to your own booking system or pricing API to pull live rates.
        Until then, mock rates from FLEET above are used (set price_range min==max
        for a fixed price rather than a range).
        """
        raise NotImplementedError("Connect to Blue Car Rental's own pricing system here.")
