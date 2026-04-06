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

    # ── Mercedes ────────────────────────────────────────────────────────────
    "mercedes benz vito":                       "Mercedes Vito",
    "mercedes-benz vito":                       "Mercedes Vito",
    "mercedes vito":                            "Mercedes Vito",
    "mercedes gle":                             "Mercedes GLE",
    "mercedes gle phev":                        "Mercedes GLE",
    "mercedes benz 350 gle phev":               "Mercedes GLE",
    "mercedes gle 350 phev":                    "Mercedes GLE",

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

    # ── Toyota Land Cruiser (additional variants) ────────────────────────────
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
    "dacia duster (older model)":                "Dacia Duster",
    "dacia duster (new model)":                  "Dacia Duster",
    "dacia duster (2022-2023) older model":      "Dacia Duster",
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
}

# ---------------------------------------------------------------------------
# Suffix patterns to strip before the exact lookup.
# Applied in order — only the first match is removed.
# This catches "(automatic)", "(manual)", "automatic", etc. that booking
# systems sometimes append to model names.
# ---------------------------------------------------------------------------
import re as _re

_STRIP_SUFFIXES = _re.compile(
    r"\s*[\(\[]?\s*"
    r"(?:plug-in hybrid|plug in hybrid|phev|plug-in|automatic|manual|auto|petrol|diesel|hybrid|electric)"
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
      4. If not found, return the cleaned name as-is.

    This function is intentionally conservative: it only maps names that are
    explicitly listed. Unknown variants are returned unchanged so they appear
    in the dashboard and can be reviewed and added to _EXACT if needed.
    """
    if not name:
        return name

    cleaned = _STRIP_SUFFIXES.sub("", name.strip()).strip()
    return _EXACT.get(cleaned.lower(), cleaned)
