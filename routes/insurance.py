"""
Insurance comparison data for all tracked Iceland car rental competitors.
Data researched April 2026 from publicly available sources.
"""

import copy
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/insurance", tags=["insurance"])

# Per-category zero-excess (full protection) daily price in ISK.
# Used by the "Price by Category" comparison table.
# None = not published / priced in foreign currency.
# Source: April 2026 research; prices reflect the full zero-excess tier per day.
CATEGORY_PRICING = {
    "Blue Car Rental": {
        "package": "Liability Waiver (Zero)",
        "note": "4,450 ISK Economy–Compact · 5,200 ISK mid-size SUV · 6,050 ISK large 4x4 & Minivan",
        "prices": {
            "Economy":  4450,
            "Compact":  4450,
            "SUV":      5200,
            "4x4":      6050,
            "Minivan":  6050,
        },
    },
    "Holdur": {
        "package": "Premium Protection",
        "note": "3,900 ISK standard cars · 6,500 ISK jeeps & large vehicles",
        "prices": {
            "Economy":  3900,
            "Compact":  3900,
            "SUV":      6500,
            "4x4":      6500,
            "Minivan":  6500,
        },
    },
    "Hertz Iceland": {
        "package": "MAX Coverage",
        "note": "4,950 ISK standard · 5,950 ISK large. CDW not included in base — add 3,190–4,090 ISK/day.",
        "prices": {
            "Economy":  4950,
            "Compact":  4950,
            "SUV":      5950,
            "4x4":      5950,
            "Minivan":  5950,
        },
    },
    "Lava Car Rental": {
        "package": "Full Protection",
        "note": "Flat 5,000 ISK/day all categories. 7 protections already in base price.",
        "prices": {
            "Economy":  5000,
            "Compact":  5000,
            "SUV":      5000,
            "4x4":      5000,
            "Minivan":  5000,
        },
    },
    "Lotus Car Rental": {
        "package": "Platinum Package",
        "note": "Flat rate all categories: 6,950 ISK/day Platinum · 4,650 ISK/day Gold · 2,190 ISK/day Silver (base).",
        "prices": {
            "Economy":  6950,
            "Compact":  6950,
            "SUV":      6950,
            "4x4":      6950,
            "Minivan":  6950,
        },
    },
    "Avis Iceland": {
        "package": "Aukin viðbótartrygging",
        "note": "4,450 ISK/day Economy & Compact · 5,350 ISK/day SUV, 4x4 & Minivan.",
        "prices": {
            "Economy":  4450,
            "Compact":  4450,
            "SUV":      5350,
            "4x4":      5350,
            "Minivan":  5350,
        },
    },
    "Go Car Rental": {
        "package": "Gold Package",
        "note": "Priced in EUR (~€25/day all categories), not ISK.",
        "prices": {
            "Economy":  None,
            "Compact":  None,
            "SUV":      None,
            "4x4":      None,
            "Minivan":  None,
        },
        "price_eur": {
            "Economy":  25,
            "Compact":  25,
            "SUV":      25,
            "4x4":      25,
            "Minivan":  None,
        },
    },
}

INSURANCE_DATA = {
    "last_updated": "April 2026",
    "disclaimer": "Prices in ISK unless noted. Verify directly with rental companies before booking — terms and prices change.",
    "protection_types": [
        {"id": "tpl",   "name": "Third-Party Liability",     "acronym": "TPL",    "description": "Mandatory by Icelandic law. Covers damage or injury to third parties."},
        {"id": "cdw",   "name": "Collision Damage Waiver",   "acronym": "CDW",    "description": "Covers repair costs if the rental vehicle is damaged in a collision. Most companies include this by default — Hertz does not."},
        {"id": "scdw",  "name": "Super CDW",                 "acronym": "SCDW",   "description": "Reduces the CDW excess/deductible significantly, lowering your out-of-pocket liability after an accident."},
        {"id": "tp",    "name": "Theft Protection",          "acronym": "TP",     "description": "Covers the vehicle if it is stolen. Personal belongings are never covered."},
        {"id": "gp",    "name": "Gravel & Glass Protection", "acronym": "GP",     "description": "Essential in Iceland. Covers windscreen, headlights, and mirrors from flying road gravel and stones."},
        {"id": "saap",  "name": "Sand & Ash Protection",     "acronym": "SAAP",   "description": "Covers volcanic ash and sandstorm damage to paint, windows, and body panels. Particularly important in South Iceland and near volcanic areas."},
        {"id": "tip",   "name": "Tire & Wheel Protection",   "acronym": "TIP",    "description": "Covers repair or replacement of tires and wheels from road hazards."},
        {"id": "pai",   "name": "Personal Accident Ins.",    "acronym": "PAI",    "description": "Covers injuries to the driver and passengers in an accident. Mandatory in Iceland for some companies."},
        {"id": "ra",    "name": "Roadside Assistance",       "acronym": "RA",     "description": "Covers towing, flat tyres, lost keys, battery jump-start, and F-road rescue."},
        {"id": "froad", "name": "F-Road Protection",         "acronym": "F-Road", "description": "Covers damage sustained on highland interior F-roads. Only available from Lotus (Gold/Platinum packages for 4x4)."},
        {"id": "river", "name": "River Crossing Protection", "acronym": "RCP",    "description": "Covers water and river crossing damage to engine, transmission, and radiator. 4x4 only. Exclusive to Lotus Platinum."},
        {"id": "zero",  "name": "Zero Excess Cover",         "acronym": "ZERO",   "description": "Reduces all covered deductibles to 0 ISK. The highest tier of coverage available from each company."},
    ],
    "companies": {
        "Blue Car Rental": {
            "color": "#2563eb",
            "website": "bluecarrental.is",
            "insurance_url": "https://www.bluecarrental.is/useful-information/insurance/",
            "highlight": "SCDW & GP included by default",
            "notes": "Liability Waiver (zero excess) also unlocks key-box self-service pickup. Prices vary by vehicle size (small / medium / large).",
            "included_base": [
                {"type": "tpl",  "deductible_isk": None,    "note": "Mandatory"},
                {"type": "cdw",  "deductible_isk": 350000,  "note": "Reduced to 90–120k ISK with the included SCDW"},
                {"type": "scdw", "deductible_label": "90k–120k ISK", "deductible_isk": 90000,  "note": "90k small cars / 120k medium-large & vans"},
                {"type": "gp",   "deductible_isk": 40000,   "note": "Windscreen, headlights, mirrors, paint"},
                {"type": "tp",   "deductible_isk": 0,       "note": "Zero deductible"},
            ],
            "packages": [
                {
                    "name": "Base Rental", "tier": "base",
                    "price_isk": None, "price_note": "Included",
                    "covers": ["tpl", "cdw", "scdw", "gp", "tp"],
                    "deductible_summary": "90k–120k ISK collision",
                },
                {
                    "name": "Sand & Ash Protection", "tier": "addon",
                    "price_isk": 1850, "price_note": "1,850 ISK/day",
                    "covers": ["saap"],
                    "deductible_summary": "90k ISK",
                },
                {
                    "name": "Roadside Assistance", "tier": "addon",
                    "price_isk": 1400, "price_note": "1,400 ISK/day",
                    "covers": ["ra"],
                    "deductible_summary": "N/A",
                },
                {
                    "name": "Liability Waiver (Zero)", "tier": "zero",
                    "price_isk": 4450, "price_note": "4,450–6,050 ISK/day",
                    "covers": ["tpl", "cdw", "scdw", "gp", "tp", "saap", "ra", "zero"],
                    "deductible_summary": "0 ISK all covered",
                },
            ],
        },
        "Holdur": {
            "color": "#22c55e",
            "website": "holdur.is",
            "insurance_url": "https://holdur.is/services/protection",
            "highlight": "Insurance provided by VÍS",
            "notes": "Deductibles differ for standard cars vs. jeeps/large vehicles. Prices shown as cars / large in package descriptions.",
            "included_base": [
                {"type": "cdw", "deductible_label": "250k–450k ISK", "deductible_isk": 250000, "note": "250k cars / 450k jeeps & large"},
                {"type": "pai", "deductible_isk": None, "note": "Included"},
                {"type": "tp",  "deductible_isk": None, "note": "Included"},
            ],
            "packages": [
                {
                    "name": "Base Rental", "tier": "base",
                    "price_isk": None, "price_note": "Included",
                    "covers": ["cdw", "pai", "tp"],
                    "deductible_summary": "250k–450k ISK collision",
                },
                {
                    "name": "Medium Protection", "tier": "addon",
                    "price_isk": 2400, "price_note": "2,400 / 4,450 ISK/day",
                    "covers": ["cdw", "scdw", "tp", "gp"],
                    "deductible_summary": "60k ISK cars / 110k ISK large",
                },
                {
                    "name": "Premium Protection", "tier": "zero",
                    "price_isk": 3900, "price_note": "3,900 / 6,500 ISK/day",
                    "covers": ["cdw", "scdw", "tp", "gp", "saap", "zero"],
                    "deductible_summary": "0 ISK all covered",
                },
            ],
        },
        "Lotus Car Rental": {
            "color": "#881337",
            "website": "lotuscarrental.is",
            "insurance_url": "https://www.lotuscarrental.is/insurance",
            "highlight": "Only company with river crossing cover",
            "notes": "Flat daily prices apply to all car categories. Platinum uniquely covers river crossings and F-roads. Deductibles: Silver 150k ISK · Gold 65k ISK · Platinum 0 ISK.",
            "included_base": [
                {"type": "tpl",  "deductible_isk": None,   "note": "Mandatory"},
                {"type": "scdw", "deductible_isk": 150000, "note": "Included as Silver Package in base rental"},
                {"type": "tp",   "deductible_isk": 0,      "note": "Zero deductible"},
            ],
            "packages": [
                {
                    "name": "Silver (Base)", "tier": "base",
                    "price_isk": 2190, "price_note": "2,190 ISK/day",
                    "covers": ["tpl", "scdw", "tp"],
                    "deductible_summary": "150k ISK collision",
                },
                {
                    "name": "Gold Package", "tier": "addon",
                    "price_isk": 4650, "price_note": "4,650 ISK/day",
                    "covers": ["tpl", "scdw", "tp", "gp", "saap", "tip", "froad"],
                    "deductible_summary": "65k ISK",
                },
                {
                    "name": "Platinum Package", "tier": "zero",
                    "price_isk": 6950, "price_note": "6,950 ISK/day",
                    "covers": ["tpl", "scdw", "tp", "gp", "saap", "tip", "froad", "river", "zero"],
                    "deductible_summary": "0 ISK (35k ISK towing only)",
                },
            ],
        },
        "Avis Iceland": {
            "color": "#ef4444",
            "website": "avis.is",
            "insurance_url": "https://www.avis.is/en/drive-avis/extras/insurances",
            "highlight": "2 size tiers: small cars vs. large",
            "notes": "Two add-on tiers on top of base. Prices split by car size: small/compact vs. SUV, 4x4 & minibus. Deductibles: base 195k ISK (small) / 360k ISK (large) · both add-on tiers reduce to 0 ISK.",
            "included_base": [
                {"type": "tpl", "deductible_isk": None,   "note": "Mandatory"},
                {"type": "pai", "deductible_isk": None,   "note": "Mandatory by Icelandic law"},
                {"type": "cdw", "deductible_label": "195k–360k ISK", "deductible_isk": 195000, "note": "195k small cars / 360k large (jeeps, minibuses, vans)"},
                {"type": "tp",  "deductible_isk": 0,      "note": "Þjófnaðartrygging — zero deductible"},
            ],
            "packages": [
                {
                    "name": "Grunntrygging (Base)", "tier": "base",
                    "price_isk": None, "price_note": "Included",
                    "covers": ["tpl", "pai", "cdw", "tp"],
                    "deductible_summary": "195k ISK (small) / 360k ISK (large)",
                },
                {
                    "name": "Viðbótartrygging", "tier": "addon",
                    "price_isk": 2700, "price_note": "2,700 / 3,600 ISK/day",
                    "covers": ["cdw", "scdw", "tp"],
                    "deductible_summary": "0 ISK collision",
                },
                {
                    "name": "Aukin viðbótartrygging", "tier": "zero",
                    "price_isk": 4450, "price_note": "4,450 / 5,350 ISK/day",
                    "covers": ["cdw", "scdw", "tp", "ra", "zero"],
                    "deductible_summary": "0 ISK all covered + roadside",
                },
            ],
        },
        "Go Car Rental": {
            "color": "#f97316",
            "website": "gocarrental.is",
            "insurance_url": "https://www.gocarrental.is/useful-information/insurances/",
            "highlight": "Prices in EUR, not ISK",
            "notes": "Insurance provider: Vörður. Unique among Iceland competitors pricing in EUR. Debit card rentals require a minimum of the Gold package (~€25/day).",
            "included_base": [
                {"type": "tpl", "deductible_isk": None, "note": "Mandatory"},
                {"type": "cdw", "deductible_label": "~€1,000", "note": "Approx. €1,000 deductible"},
                {"type": "gp",  "deductible_label": "~€1,000", "note": "Basic gravel protection, €1,000 deductible"},
            ],
            "packages": [
                {
                    "name": "Basic (Base)", "tier": "base",
                    "price_isk": None, "price_note": "Included",
                    "covers": ["tpl", "cdw", "gp"],
                    "deductible_summary": "~€1,000 collision & gravel",
                },
                {
                    "name": "Silver", "tier": "addon",
                    "price_isk": None, "price_note": "Not published",
                    "covers": ["tpl", "cdw", "scdw", "tp", "gp"],
                    "deductible_summary": "€1,000 collision / €250 gravel",
                },
                {
                    "name": "Gold", "tier": "zero",
                    "price_isk": None, "price_note": "~€25/day",
                    "covers": ["tpl", "cdw", "scdw", "tp", "gp", "zero"],
                    "deductible_summary": "€0 all covered",
                },
                {
                    "name": "Platinum", "tier": "zero",
                    "price_isk": None, "price_note": "Higher than Gold (unpublished)",
                    "covers": ["tpl", "cdw", "scdw", "tp", "gp", "saap", "tip", "zero"],
                    "deductible_summary": "€0 all covered",
                },
            ],
        },
        "Hertz Iceland": {
            "color": "#eab308",
            "website": "hertz.is",
            "insurance_url": "https://www.hertz.is/protection-information/",
            "highlight": "CDW not included in base price",
            "notes": "Most unbundled structure of all companies — CDW must be purchased separately (3,190–4,090 ISK/day). SAAP still carries a high deductible (242k–399k ISK) even when purchased standalone; only eliminated in the MAX package.",
            "included_base": [
                {"type": "tpl", "deductible_isk": None, "note": "Mandatory"},
                {"type": "pai", "deductible_isk": None, "note": "Mandatory by Icelandic law"},
            ],
            "individual_products": [
                {"type": "cdw",  "price_isk": 3190, "price_large_isk": 4090, "deductible_label": "242k–399k ISK", "deductible_isk": 242000},
                {"type": "scdw", "price_isk": 1990, "price_large_isk": 2990, "deductible_label": "30k–65k ISK",   "deductible_isk": 30000},
                {"type": "tp",   "price_isk": 990,  "price_large_isk": 990,  "deductible_label": "242k–399k ISK", "deductible_isk": 242000},
                {"type": "gp",   "price_isk": 1290, "price_large_isk": 2090, "deductible_label": "0 ISK",         "deductible_isk": 0},
                {"type": "saap", "price_isk": 1990, "price_large_isk": 2990, "deductible_label": "242k–399k ISK (high even when purchased)", "deductible_isk": 242000},
            ],
            "packages": [
                {
                    "name": "Base Rental", "tier": "base",
                    "price_isk": None, "price_note": "TPL + PAI only — CDW not included",
                    "covers": ["tpl", "pai"],
                    "deductible_summary": "Full vehicle liability (no CDW)",
                },
                {
                    "name": "Medium Package", "tier": "addon",
                    "price_isk": 2750, "price_note": "2,750 / 3,850 ISK/day",
                    "covers": ["scdw", "tp", "gp"],
                    "deductible_summary": "30k–65k ISK collision, 0 ISK windscreen",
                },
                {
                    "name": "MAX Coverage", "tier": "zero",
                    "price_isk": 4950, "price_note": "4,950 / 5,950 ISK/day",
                    "covers": ["cdw", "scdw", "tpl", "pai", "tp", "gp", "saap", "tip", "zero"],
                    "deductible_summary": "0 ISK all covered",
                },
            ],
        },
        "Lava Car Rental": {
            "color": "#a855f7",
            "website": "lavacarrental.is",
            "insurance_url": "https://lavacarrental.is/terms-extras/insurances",
            "highlight": "Most comprehensive base bundle in the market",
            "notes": "7 protections included in the base rental price — no other company includes SAAP and TIP by default. Approximately 75% of customers also purchase Full Protection.",
            "included_base": [
                {"type": "tpl",  "deductible_isk": None,   "note": "Mandatory"},
                {"type": "cdw",  "deductible_isk": 360000, "note": "Before SCDW reduction"},
                {"type": "scdw", "deductible_isk": 150000, "note": "Reduces CDW to 150k ISK"},
                {"type": "tp",   "deductible_isk": 0,      "note": "Zero deductible"},
                {"type": "gp",   "deductible_isk": 35000,  "note": "Windscreen, headlights, mirrors, hood"},
                {"type": "saap", "deductible_isk": 35000,  "note": "Sand & ash included by default — unique in market"},
                {"type": "tip",  "deductible_isk": 35000,  "note": "Tire & wheel included by default — unique in market"},
            ],
            "packages": [
                {
                    "name": "Base Rental", "tier": "base",
                    "price_isk": None, "price_note": "Included — 7 protections",
                    "covers": ["tpl", "cdw", "scdw", "tp", "gp", "saap", "tip"],
                    "deductible_summary": "150k ISK collision, 35k ISK GP/SAAP/TIP",
                },
                {
                    "name": "Full Protection", "tier": "zero",
                    "price_isk": 5000, "price_note": "5,000 ISK/day",
                    "covers": ["tpl", "cdw", "scdw", "tp", "gp", "saap", "tip", "zero"],
                    "deductible_summary": "0 ISK all covered",
                },
            ],
        },
    },
    "key_insights": [
        {
            "icon": "🏆",
            "title": "Most Comprehensive Base",
            "company": "Lava Car Rental",
            "color": "#a855f7",
            "text": "7 protections in every rental by default: CDW, SCDW, TP, GP, SAAP, Tire & TPL. No other company includes SAAP and TIP in the base price.",
        },
        {
            "icon": "⚠️",
            "title": "CDW Not Included",
            "company": "Hertz Iceland",
            "color": "#eab308",
            "text": "The only company where Collision Damage Waiver is NOT in the base price. Must be purchased separately at 3,190–4,090 ISK/day.",
        },
        {
            "icon": "🌊",
            "title": "River Crossing Cover",
            "company": "Lotus Car Rental",
            "color": "#881337",
            "text": "The only company offering river crossing protection — available exclusively in the Platinum Package for 4x4 vehicles.",
        },
        {
            "icon": "💶",
            "title": "EUR-Denominated",
            "company": "Go Car Rental",
            "color": "#f97316",
            "text": "Uniquely prices all insurance in EUR rather than ISK. Debit card rentals require minimum Gold (~€25/day). Zero-excess Gold is the most affordable published zero-excess option.",
        },
    ],
}


def _apply_overrides(base: dict, overrides: dict) -> dict:
    """
    Merge DB overrides into a deep copy of CATEGORY_PRICING.
    Overrides structure: { company: { category: {price_isk, price_note, updated_at} } }
    """
    merged = copy.deepcopy(base)
    for company, cats in overrides.items():
        if company not in merged:
            continue
        for category, override in cats.items():
            if "prices" not in merged[company]:
                merged[company]["prices"] = {}
            if override.get("price_isk") is not None:
                merged[company]["prices"][category] = override["price_isk"]
            if override.get("price_note"):
                merged[company]["note"] = override["price_note"]
            merged[company].setdefault("_overrides", {})[category] = override["updated_at"]
    return merged


@router.get("")
async def get_insurance_data():
    """Return full insurance comparison data including any saved price overrides."""
    from database import get_insurance_reviews, get_insurance_price_overrides
    reviews = await get_insurance_reviews(limit=1)
    last_reviewed = reviews[0]["reviewed_at"] if reviews else None
    overrides = await get_insurance_price_overrides()
    pricing = _apply_overrides(CATEGORY_PRICING, overrides)
    return {**INSURANCE_DATA, "category_pricing": pricing, "last_reviewed": last_reviewed}


@router.get("/category-pricing")
async def get_category_pricing():
    """Return zero-excess pricing with any saved overrides applied."""
    from database import get_insurance_price_overrides
    overrides = await get_insurance_price_overrides()
    pricing = _apply_overrides(CATEGORY_PRICING, overrides)
    return {"category_pricing": pricing, "categories": ["Economy", "Compact", "SUV", "4x4", "Minivan"]}


class PriceOverrideRequest(BaseModel):
    company: str
    category: str
    price_isk: Optional[int] = None   # None = mark as unpublished
    price_note: Optional[str] = None


@router.post("/prices")
async def save_price_override(body: PriceOverrideRequest):
    """
    Save or update a zero-excess price for one company + car category.
    Persists to DB and is applied on all subsequent /api/insurance calls.
    """
    from database import set_insurance_price_override
    valid_companies = list(CATEGORY_PRICING.keys())
    valid_categories = ["Economy", "Compact", "SUV", "4x4", "Minivan"]
    if body.company not in valid_companies:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown company. Valid: {valid_companies}")
    if body.category not in valid_categories:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown category. Valid: {valid_categories}")
    row = await set_insurance_price_override(
        company=body.company,
        category=body.category,
        price_isk=body.price_isk,
        price_note=body.price_note,
    )
    return {"message": "Price saved.", "override": row}


class ReviewRequest(BaseModel):
    reviewer: Optional[str] = ""
    notes: Optional[str] = ""
    companies_verified: Optional[list[str]] = None


@router.post("/mark-reviewed")
async def mark_insurance_reviewed(body: ReviewRequest):
    """
    Record a manual verification event — call this after reviewing company websites
    to confirm prices are current.
    """
    from database import log_insurance_review
    entry = await log_insurance_review(
        reviewer=body.reviewer or "",
        notes=body.notes or "",
        companies=body.companies_verified,
    )
    return {"message": "Insurance data marked as reviewed.", "entry": entry}


@router.get("/review-log")
async def get_review_log(limit: int = 10):
    """Return the insurance verification history."""
    from database import get_insurance_reviews
    reviews = await get_insurance_reviews(limit=limit)
    return {"reviews": reviews}
