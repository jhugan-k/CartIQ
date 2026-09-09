"""Pack-size parsing, so two offers can be compared on value rather than price.

The QuickCommerce API returns `quantity` as free text ("500 g", "1 L",
"1 Piece x 2", "172 Pages"). That makes sticker prices misleading: in a real
result, Classmate "1 Piece x 2" at Rs 48 and "1 Piece" at Rs 24 are the SAME
value, but the Rs 24 one looks half the price.

This module normalizes that text to a base unit (g / ml / piece / page) so the
agent reasons about price per unit instead of price per pack.
"""

import re

# Multiplier -> base unit. Mass normalizes to grams, volume to millilitres, and
# countables to pieces, so two packs of the same kind become comparable.
_UNITS: dict[str, tuple[float, str]] = {
    "kg": (1000.0, "g"), "kgs": (1000.0, "g"),
    "kilogram": (1000.0, "g"), "kilograms": (1000.0, "g"),
    "g": (1.0, "g"), "gm": (1.0, "g"), "gms": (1.0, "g"),
    "gram": (1.0, "g"), "grams": (1.0, "g"),
    "l": (1000.0, "ml"), "ltr": (1000.0, "ml"), "ltrs": (1000.0, "ml"),
    "litre": (1000.0, "ml"), "litres": (1000.0, "ml"),
    "liter": (1000.0, "ml"), "liters": (1000.0, "ml"),
    "ml": (1.0, "ml"),
    "piece": (1.0, "piece"), "pieces": (1.0, "piece"),
    "pc": (1.0, "piece"), "pcs": (1.0, "piece"),
    "unit": (1.0, "piece"), "units": (1.0, "piece"),
    # stationery packs price meaningfully per page, and QC returns "172 Pages".
    "page": (1.0, "page"), "pages": (1.0, "page"),
}

# "500 g", "1.5 L" — a number followed by a word. The word is kept only if it's
# a unit we know, which also skips the stray "x" in "2 x 500 ml".
_AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*([a-z]+)")
# A pack multiplier on either side of the amount: "x 2" or "2 x".
_MULTIPLIER = re.compile(r"x\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*x")

# Per-100 reads naturally for g/ml (Rs 27.4/100ml); countables read per unit.
_PER_100 = {"g", "ml"}


# turn a free-text pack size into a comparable amount in a base unit.
def parse_quantity(quantity: str | None) -> tuple[float, str] | None:
    """Parse a pack-size string into (amount_in_base_unit, base_unit).

    Returns None when there is no unit we recognise ("Pack of 2", "Assorted"),
    which callers treat as "not comparable" rather than guessing a number.
    """
    if not quantity:
        return None
    text = quantity.lower().replace("\u00d7", "x")

    # first amount whose unit we actually understand.
    match = next((m for m in _AMOUNT.finditer(text) if m.group(2) in _UNITS), None)
    if match is None:
        return None
    factor, base = _UNITS[match.group(2)]
    amount = float(match.group(1)) * factor

    # Look for a pack multiplier OUTSIDE the amount just consumed, so the 500 in
    # "2 x 500 ml" isn't mistaken for its own multiplier.
    rest = text[: match.start()] + " " + text[match.end() :]
    mult = _MULTIPLIER.search(rest)
    if mult:
        packs = float(mult.group(1) or mult.group(2))
        if packs > 0:
            amount *= packs

    return (amount, base) if amount > 0 else None


# render the comparable price the model should reason about.
def unit_price(offer_price: float | None, quantity: str | None) -> str | None:
    """Return a comparable unit price like 'Rs 27.4/100ml' or 'Rs 24/piece'.

    None when the pack size can't be parsed or there's no price — showing
    nothing beats showing a number the model would then reason from.
    """
    parsed = parse_quantity(quantity)
    if not parsed or not offer_price or offer_price <= 0:
        return None
    amount, base = parsed
    if base in _PER_100:
        return f"\u20b9{round(offer_price / amount * 100, 2):g}/100{base}"
    return f"\u20b9{round(offer_price / amount, 2):g}/{base}"
