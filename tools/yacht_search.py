# tools/yacht_search.py

"""
Mock yacht search tool for the Yacht MLS Agent POC.

This file is intentionally simple compared to a real MLS search system.

Current purpose:
- Search the local data/yachts.json file.
- Support normal hard filters like price, length, location, and cabins.
- Handle simple "near / around" language for South Florida searches.
- Return exact matches when available.
- Return close alternatives when there is no exact match.

Later, this file is the main replacement point for a real MLS API,
SQL Server query, OpenSearch query, or company backend service.
"""

import json
import re
from pathlib import Path
from typing import Any


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yachts.json"


SOUTH_FLORIDA_NEARBY_MAP = {
    "fort lauderdale": ["fort lauderdale", "miami", "palm beach", "hollywood", "pompano beach"],
    "miami": ["miami", "fort lauderdale", "palm beach"],
    "palm beach": ["palm beach", "fort lauderdale", "miami"],
}


SOFT_PREFERENCE_KEYWORDS = [
    "family-friendly",
    "family",
    "sporty",
    "sport",
    "modern",
    "sleek",
    "entertaining",
    "weekend",
    "low engine hours",
    "low hours",
    "luxury",
    "long-range",
    "cruising",
    "comfortable",
]


def load_yachts() -> list[dict[str, Any]]:
    """
    Load yacht listings from the local JSON file.
    """
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _normalize_text(value: Any) -> str:
    """
    Convert a value into lowercase searchable text.
    """
    if value is None:
        return ""
    return str(value).lower().strip()


def _split_location_keywords(location_text: str | None) -> list[str]:
    """
    Convert one location string into a list of location keywords.

    Examples:
    - "Miami and Palm Beach" -> ["Miami", "Palm Beach"]
    - "Miami, Palm Beach" -> ["Miami", "Palm Beach"]
    - "near Fort Lauderdale" -> ["Fort Lauderdale"]
    """
    if not location_text:
        return []

    cleaned = re.sub(
        r"\b(near|around|nearby|close to|preferably near|in or near)\b",
        "",
        location_text,
        flags=re.IGNORECASE,
    ).strip()

    raw_parts = re.split(r",|\band\b|\bor\b", cleaned, flags=re.IGNORECASE)

    return [part.strip() for part in raw_parts if part.strip()]


def _build_location_keywords(
    location_keyword: str | None = None,
    location_keywords: list[str] | None = None,
) -> list[str]:
    """
    Build one clean list of location keywords.

    This keeps the old location_keyword field working while also supporting
    the newer location_keywords list.
    """
    final_keywords: list[str] = []

    final_keywords.extend(_split_location_keywords(location_keyword))

    if location_keywords:
        for keyword in location_keywords:
            final_keywords.extend(_split_location_keywords(keyword))

    unique_keywords: list[str] = []

    for keyword in final_keywords:
        normalized = keyword.lower()
        if normalized not in [item.lower() for item in unique_keywords]:
            unique_keywords.append(keyword)

    return unique_keywords


def _infer_location_flexibility(
    customer_request: str | None,
    location_keyword: str | None,
    location_flexibility: str | None,
) -> str:
    """
    Decide how strict location matching should be.

    exact:
        Only match the exact city or broad region.

    nearby_ok:
        Allow nearby South Florida alternatives when the request says near,
        around, preferably near, or close to.

    statewide_ok:
        Allow broad Florida matching.
    """
    if location_flexibility:
        return location_flexibility

    combined_text = f"{customer_request or ''} {location_keyword or ''}".lower()

    if any(phrase in combined_text for phrase in ["near", "around", "nearby", "close to", "preferably near"]):
        return "nearby_ok"

    if any(phrase in combined_text for phrase in ["florida", "south florida", "fl"]):
        return "statewide_ok"

    return "exact"


def _location_matches(
    yacht_location: str,
    location_keywords: list[str],
    location_flexibility: str,
) -> tuple[bool, str]:
    """
    Check whether a yacht location matches the requested location.

    Returns:
    - bool: whether it matched
    - str: explanation of the match type
    """
    if not location_keywords:
        return True, "No location filter provided."

    yacht_location_lower = yacht_location.lower()

    for keyword in location_keywords:
        keyword_lower = keyword.lower().strip()

        if keyword_lower in ["florida", "fl", "south florida"]:
            if "fl" in yacht_location_lower or "florida" in yacht_location_lower:
                return True, "Matched broad Florida location."

        if keyword_lower in yacht_location_lower:
            return True, f"Matched requested location: {keyword}."

        if location_flexibility in ["nearby_ok", "statewide_ok"]:
            nearby_keywords = SOUTH_FLORIDA_NEARBY_MAP.get(keyword_lower, [])

            for nearby_keyword in nearby_keywords:
                if nearby_keyword in yacht_location_lower:
                    return True, f"Matched nearby alternative to {keyword}: {yacht_location}."

    return False, "Location did not match requested area."


def _request_mentions_around_length(customer_request: str | None) -> bool:
    """
    Detect whether the user is asking for an approximate length.
    """
    if not customer_request:
        return False

    request_lower = customer_request.lower()

    return any(
        phrase in request_lower
        for phrase in ["around", "about", "roughly", "approximately", "close to"]
    )


def _build_effective_length_range(
    min_length: int | None,
    max_length: int | None,
    target_length: int | None,
    customer_request: str | None,
) -> tuple[int | None, int | None, str | None]:
    """
    Convert exact or approximate length input into usable search bounds.

    Example:
    - "around 60 feet" should behave more like 45-75 feet, not exactly 60.
    """
    if target_length is not None:
        return target_length - 15, target_length + 15, f"Used approximate length range around {target_length} ft."

    mentions_around = _request_mentions_around_length(customer_request)

    if mentions_around and min_length is not None and max_length is not None and min_length == max_length:
        return min_length - 15, max_length + 15, f"Expanded exact length {min_length} ft into an approximate range."

    if mentions_around and min_length is None and max_length is not None:
        return max_length - 15, max_length + 15, f"Expanded approximate length around {max_length} ft."

    if mentions_around and min_length is not None and max_length is None:
        return min_length - 15, min_length + 15, f"Expanded approximate length around {min_length} ft."

    return min_length, max_length, None


def _extract_soft_preferences(
    customer_request: str | None,
    soft_preferences: list[str] | None,
) -> list[str]:
    """
    Build a clean list of soft preferences.

    Soft preferences are things like:
    - sporty
    - modern
    - family-friendly
    - weekend trips
    - entertaining
    """
    found_preferences: list[str] = []

    if soft_preferences:
        found_preferences.extend([pref for pref in soft_preferences if pref])

    request_lower = _normalize_text(customer_request)

    for keyword in SOFT_PREFERENCE_KEYWORDS:
        if keyword in request_lower:
            found_preferences.append(keyword)

    unique_preferences: list[str] = []

    for preference in found_preferences:
        normalized = preference.lower().strip()
        if normalized and normalized not in [item.lower() for item in unique_preferences]:
            unique_preferences.append(preference.strip())

    return unique_preferences


def _yacht_search_text(yacht: dict[str, Any]) -> str:
    """
    Build searchable text from a yacht record.
    """
    features = " ".join(yacht.get("features", []))

    return " ".join(
        [
            _normalize_text(yacht.get("name")),
            _normalize_text(yacht.get("builder")),
            _normalize_text(yacht.get("location")),
            _normalize_text(features),
            _normalize_text(yacht.get("description")),
        ]
    )


def _score_soft_preferences(
    yacht: dict[str, Any],
    soft_preferences: list[str],
) -> tuple[float, list[str]]:
    """
    Score how well a yacht matches soft preferences.

    This is not true semantic/vector search yet.
    It is a simple keyword-based approximation for the POC.
    """
    if not soft_preferences:
        return 0.0, []

    yacht_text = _yacht_search_text(yacht)

    matched_preferences: list[str] = []

    for preference in soft_preferences:
        preference_lower = preference.lower().strip()

        if preference_lower in yacht_text:
            matched_preferences.append(preference)

        elif preference_lower == "sporty" and any(word in yacht_text for word in ["sport", "sleek", "cruiser"]):
            matched_preferences.append(preference)

        elif preference_lower == "modern" and any(word in yacht_text for word in ["modern", "sleek", "2021", "2022"]):
            matched_preferences.append(preference)

        elif preference_lower == "family" and "family-friendly" in yacht_text:
            matched_preferences.append(preference)

    score = len(matched_preferences) / len(soft_preferences)

    return score, matched_preferences


def _evaluate_hard_filters(
    yacht: dict[str, Any],
    max_price: int | None,
    min_length: int | None,
    max_length: int | None,
    min_cabins: int | None,
    location_keywords: list[str],
    location_flexibility: str,
) -> tuple[bool, list[str], list[str]]:
    """
    Check hard filters and return:
    - whether the yacht passed all hard filters
    - match reasons
    - failed filter explanations
    """
    reasons: list[str] = []
    failed_filters: list[str] = []

    if max_price is not None:
        if yacht["price"] <= max_price:
            reasons.append(f"Price is within budget at ${yacht['price']:,}.")
        else:
            failed_filters.append(f"Price is above budget at ${yacht['price']:,}.")

    if min_length is not None:
        if yacht["length_ft"] >= min_length:
            reasons.append(f"Length is at least {min_length} ft.")
        else:
            failed_filters.append(f"Length is below target range at {yacht['length_ft']} ft.")

    if max_length is not None:
        if yacht["length_ft"] <= max_length:
            reasons.append(f"Length is within maximum at {yacht['length_ft']} ft.")
        else:
            failed_filters.append(f"Length is above target range at {yacht['length_ft']} ft.")

    if min_cabins is not None:
        if yacht["cabins"] >= min_cabins:
            reasons.append(f"Cabins meet requirement with {yacht['cabins']} cabins.")
        else:
            failed_filters.append(f"Cabins are below requirement with {yacht['cabins']} cabins.")

    location_match, location_reason = _location_matches(
        yacht_location=yacht["location"],
        location_keywords=location_keywords,
        location_flexibility=location_flexibility,
    )

    if location_match:
        reasons.append(location_reason)
    else:
        failed_filters.append(location_reason)

    passed = len(failed_filters) == 0

    return passed, reasons, failed_filters


def _build_result_record(
    yacht: dict[str, Any],
    match_type: str,
    hard_filter_reasons: list[str],
    failed_filters: list[str],
    soft_preferences: list[str],
    soft_score: float,
    matched_soft_preferences: list[str],
    length_note: str | None,
) -> dict[str, Any]:
    """
    Build a yacht result with extra explanation fields.

    The extra underscore-prefixed fields are for the agent/broker logic.
    They are not meant to be copied directly into customer-facing emails.
    """
    result = dict(yacht)

    result["_match_type"] = match_type
    result["_hard_filter_reasons"] = hard_filter_reasons
    result["_failed_filters"] = failed_filters
    result["_soft_preferences_checked"] = soft_preferences
    result["_matched_soft_preferences"] = matched_soft_preferences
    result["_soft_preference_score"] = round(soft_score, 2)

    if length_note:
        result["_length_note"] = length_note

    if match_type == "exact":
        result["_search_message"] = "Matched all hard filters."
    else:
        result["_search_message"] = "No exact match; this is a close alternative."

    return result


def search_yachts(
    max_price: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    location_keyword: str | None = None,
    location_keywords: list[str] | None = None,
    min_cabins: int | None = None,
    customer_request: str | None = None,
    target_length: int | None = None,
    location_flexibility: str | None = None,
    soft_preferences: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Search mock yacht listings using optional filters.

    Args:
        max_price:
            Maximum yacht price.

        min_length:
            Minimum yacht length in feet.

        max_length:
            Maximum yacht length in feet.

        location_keyword:
            Old single-location field, such as "Miami".

        location_keywords:
            New multi-location field, such as ["Miami", "Palm Beach"].

        min_cabins:
            Minimum number of cabins.

        customer_request:
            Original natural-language request. Used for small improvements like
            detecting "near" or "around."

        target_length:
            Approximate target length, such as 60 for "around 60 feet."

        location_flexibility:
            "exact", "nearby_ok", or "statewide_ok".

        soft_preferences:
            Descriptive preferences such as ["sporty", "modern"].

    Returns:
        A list of yacht records.

        If exact matches exist, only exact matches are returned.

        If no exact matches exist, close alternatives are returned with
        _match_type = "relaxed_alternative".
    """
    yachts = load_yachts()

    active_location_keywords = _build_location_keywords(
        location_keyword=location_keyword,
        location_keywords=location_keywords,
    )

    effective_location_flexibility = _infer_location_flexibility(
        customer_request=customer_request,
        location_keyword=location_keyword,
        location_flexibility=location_flexibility,
    )

    effective_min_length, effective_max_length, length_note = _build_effective_length_range(
        min_length=min_length,
        max_length=max_length,
        target_length=target_length,
        customer_request=customer_request,
    )

    active_soft_preferences = _extract_soft_preferences(
        customer_request=customer_request,
        soft_preferences=soft_preferences,
    )

    exact_results: list[dict[str, Any]] = []
    relaxed_candidates: list[dict[str, Any]] = []

    for yacht in yachts:
        passed_hard_filters, hard_filter_reasons, failed_filters = _evaluate_hard_filters(
            yacht=yacht,
            max_price=max_price,
            min_length=effective_min_length,
            max_length=effective_max_length,
            min_cabins=min_cabins,
            location_keywords=active_location_keywords,
            location_flexibility=effective_location_flexibility,
        )

        soft_score, matched_soft_preferences = _score_soft_preferences(
            yacht=yacht,
            soft_preferences=active_soft_preferences,
        )

        if passed_hard_filters:
            exact_results.append(
                _build_result_record(
                    yacht=yacht,
                    match_type="exact",
                    hard_filter_reasons=hard_filter_reasons,
                    failed_filters=[],
                    soft_preferences=active_soft_preferences,
                    soft_score=soft_score,
                    matched_soft_preferences=matched_soft_preferences,
                    length_note=length_note,
                )
            )
        else:
            relaxed_candidates.append(
                _build_result_record(
                    yacht=yacht,
                    match_type="relaxed_alternative",
                    hard_filter_reasons=hard_filter_reasons,
                    failed_filters=failed_filters,
                    soft_preferences=active_soft_preferences,
                    soft_score=soft_score,
                    matched_soft_preferences=matched_soft_preferences,
                    length_note=length_note,
                )
            )

    if exact_results:
        return sorted(
            exact_results,
            key=lambda item: (
                item.get("_soft_preference_score", 0),
                item.get("length_ft", 0),
                -item.get("price", 0),
            ),
            reverse=True,
        )

    relaxed_candidates = sorted(
        relaxed_candidates,
        key=lambda item: (
            -len(item.get("_failed_filters", [])),
            item.get("_soft_preference_score", 0),
            item.get("length_ft", 0),
            -item.get("price", 0),
        ),
        reverse=True,
    )

    return relaxed_candidates[:5]


def format_yacht_summary(yacht: dict[str, Any]) -> str:
    """
    Convert a yacht dictionary into readable text for the terminal.
    """
    features = ", ".join(yacht.get("features", []))

    return (
        f"{yacht['name']} ({yacht['year']} {yacht['builder']})\n"
        f" ID: {yacht['id']}\n"
        f" Price: ${yacht['price']:,}\n"
        f" Length: {yacht['length_ft']} ft\n"
        f" Location: {yacht['location']}\n"
        f" Cabins: {yacht['cabins']}\n"
        f" Features: {features}\n"
        f" Description: {yacht['description']}"
    )