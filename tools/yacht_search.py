# json lets Python read data from a .json file.
# Our mock yacht listings are stored in data/yachts.json.
import json

# re helps us split location text like "Miami and Palm Beach".
import re

# Path helps us build reliable file paths.
from pathlib import Path


# This creates the full path to data/yachts.json.
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yachts.json"


def load_yachts() -> list[dict]:
    """
    Load yacht listings from the local JSON file.

    Returns:
        A list of yacht dictionaries.
    """

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _split_location_keywords(location_text: str | None) -> list[str]:
    """
    Convert one location string into a list of location keywords.

    Examples:
        "Miami and Palm Beach" -> ["Miami", "Palm Beach"]
        "Miami, Palm Beach" -> ["Miami", "Palm Beach"]
        "Florida" -> ["Florida"]
    """

    if location_text is None:
        return []

    # Split on commas, "and", or "or".
    raw_parts = re.split(r",|\band\b|\bor\b", location_text, flags=re.IGNORECASE)

    # Clean up extra spaces and remove empty values.
    return [part.strip() for part in raw_parts if part.strip()]


def _build_location_keywords(
    location_keyword: str | None = None,
    location_keywords: list[str] | None = None,
) -> list[str]:
    """
    Build one clean list of location keywords.

    This keeps the old location_keyword field working while also supporting
    the new location_keywords list.
    """

    final_keywords = []

    # Support the old single-location field.
    final_keywords.extend(_split_location_keywords(location_keyword))

    # Support the new multi-location field.
    if location_keywords:
        for keyword in location_keywords:
            final_keywords.extend(_split_location_keywords(keyword))

    # Remove duplicates while preserving order.
    unique_keywords = []

    for keyword in final_keywords:
        normalized = keyword.lower()

        if normalized not in [item.lower() for item in unique_keywords]:
            unique_keywords.append(keyword)

    return unique_keywords


def _location_matches(yacht_location: str, location_keywords: list[str]) -> bool:
    """
    Check whether a yacht location matches any of the requested locations.
    """

    # If no location filter was provided, every location is acceptable.
    if not location_keywords:
        return True

    yacht_location_lower = yacht_location.lower()

    for keyword in location_keywords:
        keyword_lower = keyword.lower()

        # Treat Florida and FL as broad Florida searches.
        if keyword_lower in ["florida", "fl"]:
            if "fl" in yacht_location_lower or "florida" in yacht_location_lower:
                return True

        # Otherwise, match specific city/location text.
        elif keyword_lower in yacht_location_lower:
            return True

    return False


def search_yachts(
    max_price: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    location_keyword: str | None = None,
    location_keywords: list[str] | None = None,
    min_cabins: int | None = None,
) -> list[dict]:
    """
    Search mock yacht listings using optional filters.

    Args:
        max_price: Maximum yacht price.
        min_length: Minimum yacht length in feet.
        max_length: Maximum yacht length in feet.
        location_keyword: Old single-location field, such as "Miami".
        location_keywords: New multi-location field, such as ["Miami", "Palm Beach"].
        min_cabins: Minimum number of cabins.

    Returns:
        A list of matching yacht records.
    """

    yachts = load_yachts()
    results = []

    # Build one clean location list from both old and new inputs.
    active_location_keywords = _build_location_keywords(
        location_keyword=location_keyword,
        location_keywords=location_keywords,
    )

    for yacht in yachts:
        if max_price is not None and yacht["price"] > max_price:
            continue

        if min_length is not None and yacht["length_ft"] < min_length:
            continue

        if max_length is not None and yacht["length_ft"] > max_length:
            continue

        if not _location_matches(yacht["location"], active_location_keywords):
            continue

        if min_cabins is not None and yacht["cabins"] < min_cabins:
            continue

        results.append(yacht)

    return results


def format_yacht_summary(yacht: dict) -> str:
    """
    Convert a yacht dictionary into readable text for the terminal.
    """

    features = ", ".join(yacht["features"])

    return (
        f"{yacht['name']} ({yacht['year']} {yacht['builder']})\n"
        f"  ID: {yacht['id']}\n"
        f"  Price: ${yacht['price']:,}\n"
        f"  Length: {yacht['length_ft']} ft\n"
        f"  Location: {yacht['location']}\n"
        f"  Cabins: {yacht['cabins']}\n"
        f"  Features: {features}\n"
        f"  Description: {yacht['description']}"
    )