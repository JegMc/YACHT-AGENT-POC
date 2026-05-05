# Mock yacht listings are stored in data/yachts.json.
import json
# Path helps build reliable file paths.
from pathlib import Path


# This creates the full path to data/yachts.json.
#
# __file__ means "the current file", which is yacht_search.py.
# .resolve() gets the full absolute path.
# .parent gets the folder containing this file, which is tools/.
# .parent.parent moves up one more level to the main project folder.
#
# Final result:
# YACHT-AGENT-POC/data/yachts.json
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yachts.json"


def load_yachts() -> list[dict]:
    """
    Load yacht listings from the local JSON file.

    Returns:
        A list of yacht dictionaries.
    """

    # Open the JSON file in read mode.
    # encoding="utf-8" helps Python read text safely across different systems.
    with open(DATA_FILE, "r", encoding="utf-8") as file:

        # json.load(file) converts the JSON file into Python data.
        #
        # In this project:
        # JSON array  -> Python list
        # JSON object -> Python dictionary
        return json.load(file)


def search_yachts(
    max_price: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    location_keyword: str | None = None,
    min_cabins: int | None = None,
) -> list[dict]:
    """
    Search mock yacht listings using optional filters.

    Args:
        max_price: Maximum yacht price.
        min_length: Minimum yacht length in feet.
        max_length: Maximum yacht length in feet.
        location_keyword: A city/state/location keyword, such as "Florida" or "Miami".
        min_cabins: Minimum number of cabins.

    Returns:
        A list of matching yacht records.
    """

    # Load all yacht records from the JSON file.
    yachts = load_yachts()

    # This list will store only the yachts that match the filters.
    results = []

    # Look at each yacht one at a time.
    for yacht in yachts:

        # If max_price was provided and this yacht is too expensive,
        # skip it and move to the next yacht.
        if max_price is not None and yacht["price"] > max_price:
            continue

        # If min_length was provided and this yacht is too short,
        # skip it.
        if min_length is not None and yacht["length_ft"] < min_length:
            continue

        # If max_length was provided and this yacht is too long,
        # skip it.
        if max_length is not None and yacht["length_ft"] > max_length:
            continue

        # If a location keyword was provided, check whether it matches
        # the yacht's location.
        if location_keyword is not None:
            location_text = yacht["location"].lower()
            keyword = location_keyword.lower()

            # Our data uses "FL" instead of spelling out "Florida".
            # This lets a search for "Florida" match locations like "Miami, FL".
            if keyword == "florida":
                if "fl" not in location_text and "florida" not in location_text:
                    continue

            # For any other keyword, check whether it appears in the location text.
            # Example: "Miami" should match "Miami, FL".
            elif keyword not in location_text:
                continue

        # If min_cabins was provided and this yacht has too few cabins,
        # skip it.
        if min_cabins is not None and yacht["cabins"] < min_cabins:
            continue

        # If the yacht passed every filter above, add it to the results list.
        results.append(yacht)

    # Return all yachts that matched the search.
    return results


def format_yacht_summary(yacht: dict) -> str:
    """
    Convert a yacht dictionary into readable text for the terminal.
    """

    # The features are stored as a list.
    # Example:
    # ["flybridge", "family-friendly", "modern interior"]
    #
    # This joins them into one readable string:
    # "flybridge, family-friendly, modern interior"
    features = ", ".join(yacht["features"])

    # Return one formatted block of text describing the yacht.
    #
    # f-strings let us insert values from the yacht dictionary directly
    # into the text.
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