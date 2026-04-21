"""
Canonical car model name normaliser for Blue Rental Intelligence.

Single source of truth: maps any name variant that may come from a live
website scrape or a FLEET definition → the standardised display name used
for cross-competitor grouping in the dashboard.

Usage
-----
    from canonical import canonicalize

    canonicalize("Toyota Landcruiser 150")          # → "Toyota Land Cruiser 150"
    canonicalize("Volkswagen Caravelle 4x4")         # → "VW Caravelle"
    canonicalize("Kia Ceed Sportswagon")             # → "Kia Ceed Wagon"
    canonicalize("Jeep Wrangler RUBICON")            # → "Jeep Wrangler"
    canonicalize("Toyota Aygo Automatic")            # → "Toyota Aygo"
    canonicalize("Some Totally Unknown Model")       # → "Some Totally Unknown Model"

Adding new mappings
-------------------
Just append an entry to _EXACT (keyed on the lowercased, stripped variant).
The value is the canonical display name, capitalized exactly as you want
it to appear in the UI.
"""

# ---------------------------------------------------------------------------
# Exact-match lookup  (key = lowercase + stripped variant)
# ---------------------------------------------------------------------------
_EXACT: dict[str, str] = {

    # ── Toyota Land Cruiser ─────────────────────────────────────────────────
    "toyota land cruiser":                      "Toyota Land Cruiser 150",
    "toyota land cruiser 150":                  "Toyota Land Cruiser 150",
    "toyota landcruiser 150":                   "Toyota Land Cruiser 150",
    "toyota land cruiser 150 4x4":              "Toyota Land Cruiser 150",
    "toyota land cruiser 150, 7 seater":        "Toyota Land Cruiser 150",
    "toyota land cruiser 150 (7 seater)":       "Toyota Land Cruiser 150",
    "toyota land cruiser 150, 7 seater 4x4":    "Toyota Land Cruiser 150",
    "toyota land cruiser adventure":            "Toyota Land Cruiser 250",
    "toyota land cruiser 250":                  "Toyota Land Cruiser 250",
    "toyota landcruiser 250":                   "Toyota Land Cruiser 250",
    "toyota land cruiser 250 4x4":              "Toyota Land Cruiser 250",

    # ── Toyota Highlander ───────────────────────────────────────────────────
    "toyota highlander":                        "Toyota Highlander",
    "toyota highlander gx":                     "Toyota Highlander",
    "toyota highlander gx 4x4":                 "Toyota Highlander",

    # ── Toyota Hilux ────────────────────────────────────────────────────────
    "toyota hilux":                             "Toyota Hilux",
    "toyota hilux 4x4":                         "Toyota Hilux",

    # ── Toyota RAV4 ─────────────────────────────────────────────────────────
    "toyota rav4":                              "Toyota RAV4",
    "toyota rav4 4x4":                          "Toyota RAV4",

    # ── Toyota Yaris Cross ──────────────────────────────────────────────────
    "toyota yaris cross":                       "Toyota Yaris Cross",
    "toyota yaris cross 4x4":                   "Toyota Yaris Cross",

    # ── Toyota Corolla ──────────────────────────────────────────────────────
    "toyota corolla wagon":                     "Toyota Corolla Wagon",

    # ── VW / Volkswagen ─────────────────────────────────────────────────────
    "volkswagen caravelle":                     "VW Caravelle",
    "volkswagen caravelle 4x4":                 "VW Caravelle",
    "vw caravelle":                             "VW Caravelle",
    "volkswagen golf":                          "VW Golf",
    "vw golf":                                  "VW Golf",
    "volkswagen california 4x4":                "VW California",
    "volkswagen california":                    "VW California",

    # ── Mercedes ────────────────────────────────────────────────────────────
    "mercedes benz vito":                       "Mercedes Vito",
    "mercedes-benz vito":                       "Mercedes Vito",
    "mercedes vito":                            "Mercedes Vito",
    "mercedes gle":                             "Mercedes GLE",
    "mercedes gle phev":                        "Mercedes GLE",
    "mercedes benz gle":                        "Mercedes GLE",
    "mercedes benz gle plug-in hybrid":         "Mercedes GLE",
    "mercedes benz 350 gle phev":               "Mercedes GLE",
    "mercedes gle 350 phev":                    "Mercedes GLE",
    "mercedes-benz sprinter":                   "Mercedes Sprinter",
    "mercedes benz sprinter":                   "Mercedes Sprinter",
    "mercedes sprinter":                        "Mercedes Sprinter",

    # ── Land Rover ──────────────────────────────────────────────────────────
    "land rover discovery sport":               "Land Rover Discovery Sport",
    "land rover discovery sport 4x4":           "Land Rover Discovery Sport",

    # ── Range Rover ─────────────────────────────────────────────────────────
    "range rover sport":                        "Range Rover Sport",

    # ── Kia Ceed variants ───────────────────────────────────────────────────
    "kia ceed wagon":                           "Kia Ceed Wagon",
    "kia ceed sportswagon":                     "Kia Ceed Wagon",

    # ── Skoda Octavia variants ──────────────────────────────────────────────
    "skoda octavia wagon":                      "Skoda Octavia Wagon",
    "skoda octavia combi":                      "Skoda Octavia Wagon",
    "skoda octavia station":                    "Skoda Octavia Wagon",

    # ── Renault Megane ──────────────────────────────────────────────────────
    "renault megane wagon":                     "Renault Megane Wagon",

    # ── Hyundai i30 ─────────────────────────────────────────────────────────
    "hyundai i30 wagon":                        "Hyundai i30",

    # ── Tesla ───────────────────────────────────────────────────────────────
    "tesla model 3 long range":                 "Tesla Model 3",
    "tesla model 3 long range 4x4":             "Tesla Model 3",

    # ── Dacia ───────────────────────────────────────────────────────────────
    "dacia sandero stepway":                    "Dacia Sandero",
    "dacia duster 4x4":                         "Dacia Duster",

    # ── Suzuki ──────────────────────────────────────────────────────────────
    "suzuki vitara 4x4":                        "Suzuki Vitara",

    # ── Kia ─────────────────────────────────────────────────────────────────
    "kia sportage 4x4":                         "Kia Sportage",
    "kia sorento 4x4":                          "Kia Sorento",

    # ── Jeep ────────────────────────────────────────────────────────────────
    "jeep wrangler rubicon":                    "Jeep Wrangler",
    "jeep wrangler rubicon 4xe":                "Jeep Wrangler",
    "jeep wrangler 4xe":                        "Jeep Wrangler",
    "jeep renegade 4x4":                        "Jeep Renegade",
    "jeep compass 4x4":                         "Jeep Compass",

    # ── Subaru ──────────────────────────────────────────────────────────────
    "subaru forester 4x4":                      "Subaru Forester",

    # ── Honda ───────────────────────────────────────────────────────────────
    "honda cr-v 4x4":                           "Honda CR-V",

    # ── Lexus ───────────────────────────────────────────────────────────────
    "lexus ux":                                 "Lexus UX250H",
    "lexus ux250h":                             "Lexus UX250H",
    "lexus ux250h 4x4":                         "Lexus UX250H",
    "lexus ux 250h":                            "Lexus UX250H",
    "lexus ux 250h 4x4":                        "Lexus UX250H",

    # ── Mitsubishi ──────────────────────────────────────────────────────────
    "mitsubishi outlander phev":                "Mitsubishi Outlander",
    "mitsubishi outlander":                     "Mitsubishi Outlander",

    # ── Opel ────────────────────────────────────────────────────────────────
    "opel corsa electric":                      "Opel Corsa",
    "opel corsa":                               "Opel Corsa",

    # ── Nissan ──────────────────────────────────────────────────────────────
    "nissan x-trail":                           "Nissan X-Trail",
    "nissan ariya awd suv":                     "Nissan Ariya",
    "nissan ariya awd suv electric":            "Nissan Ariya",
    "nissan ariya awd":                         "Nissan Ariya",

    # ── Toyota Land Cruiser (additional variants) ────────────────────────────
    "toyota land cruiser adventure \"35":        "Toyota Land Cruiser 250",
    "toyota landcruiser":                        "Toyota Land Cruiser 150",
    "5 seats toyota land cruiser":               "Toyota Land Cruiser 150",
    "5 seat toyota land cruiser":                "Toyota Land Cruiser 150",
    "toyota land cruiser 250 adventure":         "Toyota Land Cruiser 250",

    # ── Land Rover (additional variants) ────────────────────────────────────
    "land rover defender":                       "Land Rover Defender",
    "land rover defender 110":                   "Land Rover Defender",
    "land rover defender plug-in hybrid":        "Land Rover Defender",
    "land rover discovery":                      "Land Rover Discovery",
    "land rover discovery 5":                    "Land Rover Discovery",

    # ── BMW ─────────────────────────────────────────────────────────────────
    "bmw x3":                                    "BMW X3",
    "bmw x3 m sport":                            "BMW X3",
    "bmw x5":                                    "BMW X5",
    "bmw x5 plug-in hybrid":                     "BMW X5",

    # ── Kia (additional variants) ────────────────────────────────────────────
    "kia sportage":                              "Kia Sportage",
    "kia sorento":                               "Kia Sorento",
    "kia sorento plug-in hybrid":                "Kia Sorento",

    # ── Hyundai (additional variants) ───────────────────────────────────────
    "hyundai i30 station":                       "Hyundai i30",
    "hyundai tucson":                            "Hyundai Tucson",
    "hyundai tucson plug-in hybrid":             "Hyundai Tucson",

    # ── Dacia (additional variants) ──────────────────────────────────────────
    "dacia duster":                              "Dacia Duster",
    "dacia duster (older model)":                "Dacia Duster (Older Model)",
    "dacia duster (new model)":                  "Dacia Duster",
    "dacia duster (2022-2023) older model":      "Dacia Duster (Older Model)",
    "dacia bigster":                             "Dacia Bigster",

    # ── Honda ───────────────────────────────────────────────────────────────
    "honda cr-v":                                "Honda CR-V",

    # ── MG ──────────────────────────────────────────────────────────────────
    "mg ehs":                                    "MG EHS",

    # ── VW / Volkswagen (additional variants) ───────────────────────────────
    "vw transporter":                            "VW Transporter",
    "volkswagen transporter":                    "VW Transporter",
    "volkswagen transporter passenger van":      "VW Transporter",
    "vw transporter passenger van":              "VW Transporter",
    "vw transporter 4wd passenger van":          "VW Transporter",
    "volkswagen transporter 4wd passenger van":  "VW Transporter",
    "vw caravelle 9 seater":                     "VW Caravelle",
    "volkswagen caravelle 9 seater":             "VW Caravelle",

    # ── Ford ────────────────────────────────────────────────────────────────
    "ford transit":                              "Ford Transit",
    "ford transit 9 seater":                     "Ford Transit",
    "ford transit 12 seater":                    "Ford Transit",
    "ford transit 17 seater":                    "Ford Transit",

    # ── Mercedes (additional variants) ──────────────────────────────────────
    "mercedes sprinter":                         "Mercedes Sprinter",
    "mercedes-benz sprinter":                    "Mercedes Sprinter",
    "mercedes-benz sprinter 15 seater":          "Mercedes Sprinter",
    "mercedes benz sprinter":                    "Mercedes Sprinter",
    "mercedes-benz sprinter 4wd":                "Mercedes Sprinter",
    "mercedes sprinter 4wd passenger van":       "Mercedes Sprinter",
    "mercedes-benz sprinter 4wd passenger van":  "Mercedes Sprinter",
    "mercedes benz sprinter 4wd passenger van":  "Mercedes Sprinter",

    # ── Renault Trafic ──────────────────────────────────────────────────────
    "renault trafic":                            "Renault Trafic",

    # ── Kia Cee'd (Caren API uses apostrophe; FLEET uses "Ceed") ────────────
    "kia cee'd":                                 "Kia Ceed",
    "kia cee'd sportswagon":                     "Kia Ceed Wagon",

    # ── Holdur live API variants ─────────────────────────────────────────────
    "mitsubishi outlander phev 4x4":             "Mitsubishi Outlander",
    "land rover discovery 4x4":                  "Land Rover Discovery",
    "land rover defender 4x4":                   "Land Rover Defender",
    "skoda octavia combi 4x4":                   "Skoda Octavia Wagon",
    "kia sportage phev 4x4":                     "Kia Sportage",
    "kia sportage 4x4":                          "Kia Sportage",
    "suzuki jimny 4x4":                          "Suzuki Jimny",
    "dacia duster 4x4":                          "Dacia Duster",
    "suzuki vitara 4x4":                         "Suzuki Vitara",
    "toyota rav4 4x4":                           "Toyota RAV4",
    "volkswagen id.4 2wd 77kw":                  "VW ID.4",
    "volkswagen id.4 gtx":                       "VW ID.4",
    "volkswagen id.4 gtx awd":                   "VW ID.4",
    "vw id.4 ev awd":                            "VW ID.4",
    "vw id.4 ev":                                "VW ID.4",
    "vw id.4 ev awd electric":                   "VW ID.4",
    "volkswagen caddy maxi":                     "VW Caddy Maxi",
    "renault trafic lll":                        "Renault Trafic",
    "mercedes benz 350 gle phev":                "Mercedes GLE",
    "mercedes benz 350 gle phev 4x4":            "Mercedes GLE",
    "byd dolphin 60kw":                          "BYD Dolphin",
    "kia ev3 82kw":                              "Kia EV3",
    "jm - ford tourneo":                         "Ford Tourneo",

    # ── Blue Car Rental live API variants ───────────────────────────────────
    "dacia duster used model":                   "Dacia Duster (Older Model)",
    "toyota rav4 used model":                    "Toyota RAV4 (Older Model)",
    "toyota rav4 - 4x4":                         "Toyota RAV4",
    "toyota rav4 - 4x4 (older model)":           "Toyota RAV4 (Older Model)",
    "suzuki vitara mt":                          "Suzuki Vitara",
    "suzuki vitara 4x4 (older model)":           "Suzuki Vitara (Older Model)",

    # ── Lotus live API variants (long descriptive names) ────────────────────
    "kia sorento 4x4 - 7 seats":                 "Kia Sorento",
    "toyota highlander gx 4x4 - 7 seats":        "Toyota Highlander",
    "toyota hilux 4x4 double cap w/hardtop -":   "Toyota Hilux",
    "toyota land cruiser 150 4x4 - 7 seats":     "Toyota Land Cruiser 150",
    'toyota land cruiser 4x4 35" modified super jeep': "Toyota Land Cruiser 150",
    "toyota land cruiser 250 4x4 - 7 seats":     "Toyota Land Cruiser 250",
    "land rover defender 4x4":                   "Land Rover Defender",
    "tesla model y - long range 4x4":            "Tesla Model Y",
    "tesla model 3 - long range 4x4":            "Tesla Model 3",
    "suzuki jimny 4x4 - 2 seats only":           "Suzuki Jimny",
    "suzuki jimny 4x4 (manual) - 2 seats only":  "Suzuki Jimny",
    "suzuki jimny 4x4 - 2 seats only (older model)": "Suzuki Jimny (Older Model)",
    "volkswagen caravelle 4x4 - 9 seater":       "VW Caravelle",
    "mercedes benz vito tourer 4x4 - 9 seater":  "Mercedes Vito",

    # ── Sixt Iceland / Enterprise Iceland models ─────────────────────────────
    "volkswagen tiguan":                         "VW Tiguan",
    "volkswagen t-roc":                          "VW T-Roc",
    "volkswagen t roc":                          "VW T-Roc",
    "vw tiguan":                                 "VW Tiguan",
    "vw t-roc":                                  "VW T-Roc",
    "seat leon":                                 "Seat Leon",
    "ford focus":                                "Ford Focus",
    "ford focus wagon":                          "Ford Focus",
    "audi a3":                                   "Audi A3",
    "audi a3 sportback":                         "Audi A3",
    "audi q5":                                   "Audi Q5",
    "audi q7":                                   "Audi Q7",
    "bmw x1":                                    "BMW X1",
    "volvo xc90":                                "Volvo XC90",
    "volvo xc60":                                "Volvo XC60",
    "toyota corolla sedan":                      "Toyota Corolla",
    "kia picanto":                               "Kia Picanto",
    "hyundai i20":                               "Hyundai i20",
    "renault megane e-tech":                     "Renault Megane",
    "opel astra":                                "Opel Astra",
    "peugeot 308":                               "Peugeot 308",
    "ford tourneo":                              "Ford Tourneo",
    "ford tourneo connect":                      "Ford Tourneo",

    # ── Avis Iceland ─────────────────────────────────────────────────────────
    "volkswagen polo":                           "VW Polo",

    # ── Lava Car Rental models ────────────────────────────────────────────────
    "toyota aygo x":                             "Toyota Aygo X",
    "mg4":                                       "MG4",
    "tesla model y (awd)":                       "Tesla Model Y",
    "renault kangoo campervan":                  "Renault Kangoo",
}

# ---------------------------------------------------------------------------
# Canonical category map — single source of truth for car → category.
# When a canonical name is resolved, this overrides whatever the scraper
# assigned. Categories: Economy, Compact, SUV, 4x4, Minivan
# ---------------------------------------------------------------------------
CANONICAL_CATEGORIES: dict[str, str] = {
    # ── Economy (city cars, superminis, small hatchbacks) ────────────────────
    "Toyota Aygo":           "Economy",
    "Toyota Aygo X":         "Economy",
    "Toyota Yaris":          "Economy",
    "Hyundai i10":           "Economy",
    "Hyundai i20":           "Economy",
    "Suzuki Swift":          "Economy",
    "Kia Rio":               "Economy",
    "Kia Ceed":              "Economy",
    "VW Polo":               "Economy",
    "Dacia Sandero":         "Economy",
    "Opel Corsa":            "Economy",
    "Renault Clio":          "Economy",
    "Renault Zoe":           "Economy",
    "BYD Dolphin":           "Economy",
    "Kia EV3":               "Economy",
    "MG4":                   "Economy",
    "Smart #5":              "Economy",

    "Kia Picanto":           "Economy",
    "Opel Astra":            "Economy",
    "Peugeot 308":           "Economy",

    # ── Compact (mid-size sedans, wagons, small crossovers) ─────────────────
    "Dacia Jogger":          "Compact",
    "Kia Stonic":            "Compact",
    "Kia XCeed":             "Compact",
    "Kia Ceed Wagon":        "Compact",
    "VW Golf":               "Compact",
    "VW ID.3":               "Compact",
    "Toyota Corolla":        "Compact",
    "Toyota Corolla Wagon":  "Compact",
    "Toyota Corolla Sedan":  "Compact",
    "Toyota Yaris Cross":    "Compact",
    "Hyundai i30":           "Compact",
    "Skoda Octavia":         "Compact",
    "Skoda Octavia Wagon":   "Compact",
    "Renault Captur":        "Compact",
    "Renault Megane":        "Compact",
    "Renault Megane Wagon":  "Compact",
    "Mazda CX-30":           "Compact",
    "Tesla Model 3":         "Compact",
    "Seat Leon":             "Compact",
    "Ford Focus":            "Compact",
    "Audi A3":               "Compact",
    "VW T-Roc":              "Compact",

    # ── SUV (crossovers, mid-size SUVs) ─────────────────────────────────────
    "Dacia Duster":                "SUV",
    "Dacia Duster (Older Model)":  "SUV",
    "Dacia Bigster":               "SUV",
    "Dacia Duster Camping":        "SUV",
    "Suzuki Vitara":               "SUV",
    "Suzuki Vitara (Older Model)": "SUV",
    "Suzuki Jimny":                "SUV",
    "Suzuki Jimny (Older Model)":  "SUV",
    "Kia Sportage":          "SUV",
    "Toyota RAV4":                "SUV",
    "Toyota RAV4 (Older Model)":  "SUV",
    "Hyundai Tucson":        "SUV",
    "Nissan Qashqai":        "SUV",
    "Nissan Ariya":          "SUV",
    "Jeep Renegade":         "SUV",
    "Jeep Compass":          "SUV",
    "Subaru Forester":       "SUV",
    "Mitsubishi Eclipse Cross": "SUV",
    "Lexus UX250H":          "SUV",
    "MG ZS":                 "SUV",
    "MG EHS":                "SUV",
    "Subaru XV":             "SUV",
    "Kia EV6":               "SUV",
    "Tesla Model Y":         "SUV",
    "Renault Koleos":        "SUV",
    "VW ID.4":               "SUV",
    "VW Tiguan":             "SUV",
    "Skoda Kodiaq":          "SUV",
    "Audi Q5":               "SUV",
    "BMW X1":                "SUV",

    # ── 4x4 (large SUVs, off-road / F-road capable) ────────────────────────
    "Toyota Land Cruiser 150": "4x4",
    "Toyota Land Cruiser 250": "4x4",
    "Toyota Land Cruiser 4x4 35\" Modified Super Jeep": "4x4",
    "Toyota Land Cruiser 4x4 35\u201d Modified Super Jeep": "4x4",
    "Toyota Hilux":          "4x4",
    "Toyota Hilux Double Cab": "4x4",
    "Toyota Hilux Camper":   "4x4",
    "Toyota Hilux 4x4 Camper": "4x4",
    "Toyota Highlander":     "4x4",
    "Kia Sorento":           "4x4",
    "Hyundai Santa Fe":      "4x4",
    "Nissan X-Trail":        "4x4",
    "Land Rover Defender":   "4x4",
    "Land Rover Discovery":  "4x4",
    "Land Rover Discovery Sport": "4x4",
    "Land Rover Discovery Luxury 4x4 - 7 seats": "4x4",
    "Range Rover Sport":     "4x4",
    "Honda CR-V":            "4x4",
    "Jeep Wrangler":         "4x4",
    "BMW X3":                "4x4",
    "BMW X5":                "4x4",
    "Audi Q7":               "4x4",
    "Volvo XC90":            "4x4",
    "Volvo XC60":            "4x4",
    "Mercedes GLE":          "4x4",
    "Mitsubishi Outlander":  "4x4",
    "Dacia Duster 4x4 + Roof Tent": "4x4",
    "Toyota Rav4 4x4 + Roof Tent (Older Model)": "4x4",

    # ── Minivan (people carriers, passenger vans) ───────────────────────────
    "VW Caravelle":          "Minivan",
    "VW Caddy Maxi":         "Minivan",
    "VW Caddy Maxi 7 seater": "Minivan",
    "VW Transporter":        "Minivan",
    "VW California":         "Minivan",
    "Ford Tourneo":          "Minivan",
    "Ford Transit":          "Minivan",
    "Toyota Proace":         "Minivan",
    "Renault Trafic":        "Minivan",
    "Renault Kangoo":        "Minivan",
    "Mercedes Vito":         "Minivan",
    "Mercedes Sprinter":     "Minivan",
    "Fiat Benivan 160 Motorhome": "Minivan",
}


def canonicalize_category(canonical_name: str, scraper_category: str = "") -> str:
    """
    Return the correct category for a canonical car name.
    Falls back to the scraper-provided category if the name is unknown.
    """
    return CANONICAL_CATEGORIES.get(canonical_name, scraper_category)


# ---------------------------------------------------------------------------
# Suffix patterns to strip before the exact lookup.
# Applied in order — only the first match is removed.
# This catches "(automatic)", "(manual)", "automatic", etc. that booking
# systems sometimes append to model names.
# ---------------------------------------------------------------------------
import re as _re

_STRIP_SUFFIXES = _re.compile(
    r"\s*[\(\[]?\s*"
    r"(?:plug-in hybrid|plug in hybrid|phev|plug-in|automatic|manual|auto|petrol|diesel|hybrid|electric|awd|4wd)"
    r"\s*[\)\]]?\s*$",
    _re.IGNORECASE,
)


def canonicalize(name: str) -> str:
    """
    Return the canonical display name for a car model.

    Steps:
      1. Strip surrounding whitespace.
      2. Strip trailing transmission/fuel suffixes (e.g. "(Automatic)").
      3. Look up the result in the exact-match table (case-insensitive).
      4. If not found, try the apostrophe-free variant (handles "Cee'd" → "Ceed").
      5. If still not found, return the cleaned name as-is.

    This function is intentionally conservative: it only maps names that are
    explicitly listed. Unknown variants are returned unchanged so they appear
    in the dashboard and can be reviewed and added to _EXACT if needed.
    """
    if not name:
        return name

    cleaned = _STRIP_SUFFIXES.sub("", name.strip()).strip()
    key = cleaned.lower()
    result = _EXACT.get(key)
    if result:
        return result
    # Try without apostrophes — catches "Kia Cee'd" matching "kia ceed" etc.
    key_no_apos = key.replace("'", "")
    if key_no_apos != key:
        result = _EXACT.get(key_no_apos)
        if result:
            return result
    return cleaned
