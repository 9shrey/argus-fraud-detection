"""Static reference data for the synthetic transaction generator.

Merchant names are generic/fictional by design — this project scores a
believable transaction stream, not real brand data.
"""

from __future__ import annotations

CITIES_HOME = [
    "Bengaluru",
    "Mumbai",
    "Delhi",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Gurugram",
    "Noida",
    "Jaipur",
    "Kochi",
]

# Used only by fraud scenarios (impossible-travel / account-takeover) to place
# a transaction somewhere the user has never transacted from before.
CITIES_ANOMALOUS = ["Lagos", "Moscow", "Manila", "Bucharest", "Ho Chi Minh City", "Nairobi"]

CHANNELS = ["upi", "card_present", "card_not_present", "netbanking"]
CHANNEL_WEIGHTS = [0.55, 0.15, 0.22, 0.08]

MERCHANTS_BY_CATEGORY: dict[str, list[str]] = {
    "groceries": ["QuickCart Mart", "DailyBasket", "FreshFields Grocers"],
    "food_delivery": ["Swift Eats", "TiffinBox Express", "UrbanPlate"],
    "ride_hailing": ["MetroCab", "GoRide", "CityHop"],
    "electronics": ["ByteBazaar", "CircuitPoint", "GadgetGrove"],
    "fashion": ["ThreadLine", "UrbanStitch", "WardrobeWorks"],
    "utilities": ["PowerGrid Pay", "AquaBill", "CityUtilities"],
    "entertainment": ["StreamNow", "CineHouse", "PlayVerse"],
    "travel": ["SkyTrail Bookings", "RailEase", "WanderWay"],
    "pharmacy": ["CarePlus Pharmacy", "MedQuick", "HealthPoint"],
    "fuel": ["FuelStop", "PetroPoint", "EnergyMart"],
    "recharge_bills": ["TeleTop Recharge", "BillEase", "ConnectPay"],
    "jewellery": ["GoldLeaf Jewels", "LustreGems", "OrnateJewels"],
    "home_services": ["HomeFix Services", "TaskEase", "handyworks"],
    "education": ["LearnSphere", "SkillForge", "EduPay"],
    "gaming": ["PlayCredits", "GameVault Wallet", "ArenaTopUp"],
}

MERCHANT_CATEGORIES = list(MERCHANTS_BY_CATEGORY.keys())

# Categories disproportionately abused in card-testing / cash-out fraud —
# high resale value, low friction, easy to launder through.
HIGH_ABUSE_CATEGORIES = ["gaming", "jewellery", "electronics", "recharge_bills"]
