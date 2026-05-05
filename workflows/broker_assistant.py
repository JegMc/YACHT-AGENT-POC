# Import the yacht search tool.
from tools.yacht_search import search_yachts

# Import the email drafting tool.
from tools.email_drafting import draft_customer_email


def build_search_summary(
    max_price: int | None,
    min_length: int | None,
    max_length: int | None,
    location_keyword: str | None,
    min_cabins: int | None,
) -> str:
    """
    Create a readable sentence describing the user's search filters.

    This summary is used inside the email draft.
    """

    # Store each active search filter as a piece of text.
    summary_parts = []

    if max_price is not None:
        summary_parts.append(f"priced up to ${max_price:,}")

    if min_length is not None and max_length is not None:
        summary_parts.append(f"between {min_length} and {max_length} feet")

    elif min_length is not None:
        summary_parts.append(f"at least {min_length} feet")

    elif max_length is not None:
        summary_parts.append(f"up to {max_length} feet")

    if location_keyword is not None:
        summary_parts.append(f"in or near {location_keyword}")

    if min_cabins is not None:
        summary_parts.append(f"with at least {min_cabins} cabins")

    if not summary_parts:
        return "general yacht search with no specific filters"

    return ", ".join(summary_parts)


def run_broker_assistant_workflow(
    customer_name: str,
    max_price: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    location_keyword: str | None = None,
    min_cabins: int | None = None,
) -> dict:
    """
    Run the broker assistant workflow.

    This function is the reusable core of the prototype.

    It does not ask for terminal input.
    It does not print to the terminal.
    It does not save files.

    It only:
        1. Searches yacht listings
        2. Builds a search summary
        3. Drafts a customer email
        4. Returns a structured result dictionary

    This makes it reusable later for:
        - command-line demos
        - FastAPI endpoints
        - Postman testing
        - future AI agent calls
    """

    # Store the search filters in a dictionary.
    search_filters = {
        "max_price": max_price,
        "min_length": min_length,
        "max_length": max_length,
        "location_keyword": location_keyword,
        "min_cabins": min_cabins,
    }

    # Search the mock yacht data.
    matched_yachts = search_yachts(
        max_price=max_price,
        min_length=min_length,
        max_length=max_length,
        location_keyword=location_keyword,
        min_cabins=min_cabins,
    )

    # Create a readable explanation of the filters.
    search_summary = build_search_summary(
        max_price=max_price,
        min_length=min_length,
        max_length=max_length,
        location_keyword=location_keyword,
        min_cabins=min_cabins,
    )

    # Draft a customer-facing email.
    draft_email = draft_customer_email(
        customer_name=customer_name,
        yachts=matched_yachts,
        search_summary=search_summary,
    )

    # For now, emails always require human approval.
    requires_approval = True

    # Return the full structured result.
    return {
        "customer_name": customer_name,
        "search_filters": search_filters,
        "search_summary": search_summary,
        "matched_yacht_count": len(matched_yachts),
        "matched_yachts": matched_yachts,
        "draft_email": draft_email,
        "requires_approval": requires_approval,
        "status": "pending_human_review",
    }