# Import the formatting function so we can print readable yacht summaries.
from tools.yacht_search import format_yacht_summary

# Import the output saving function.
from tools.output_writer import save_agent_run

# Import the reusable broker assistant workflow.
from workflows.broker_assistant import run_broker_assistant_workflow


def get_optional_int(prompt: str) -> int | None:
    """
    Ask the user for a number.

    If the user presses Enter without typing anything,
    return None.

    None means:
        "Do not use this filter."
    """

    user_input = input(prompt).strip()

    if user_input == "":
        return None

    return int(user_input)


def get_optional_text(prompt: str) -> str | None:
    """
    Ask the user for text.

    If the user presses Enter without typing anything,
    return None.
    """

    user_input = input(prompt).strip()

    if user_input == "":
        return None

    return user_input


def print_search_criteria(result: dict) -> None:
    """
    Print the search criteria from the structured result.
    """

    # Pull the nested search_filters dictionary out of the result.
    filters = result["search_filters"]

    print("Search Criteria:")
    print(f"- Max price: {filters['max_price'] if filters['max_price'] is not None else 'Any'}")
    print(f"- Minimum length: {filters['min_length'] if filters['min_length'] is not None else 'Any'}")
    print(f"- Maximum length: {filters['max_length'] if filters['max_length'] is not None else 'Any'}")
    print(f"- Location: {filters['location_keyword'] if filters['location_keyword'] is not None else 'Any'}")
    print(f"- Minimum cabins: {filters['min_cabins'] if filters['min_cabins'] is not None else 'Any'}")
    print()


def print_matched_yachts(result: dict) -> None:
    """
    Print the matched yachts from the structured result.
    """

    # Pull the matched yacht list out of the result.
    matched_yachts = result["matched_yachts"]

    if not matched_yachts:
        print("No matching yachts found.")
        return

    print(f"Found {len(matched_yachts)} matching yacht(s):")
    print()

    for index, yacht in enumerate(matched_yachts, start=1):
        print(f"Result {index}")
        print("-" * 40)
        print(format_yacht_summary(yacht))
        print()


def print_email_draft(result: dict) -> None:
    """
    Print the drafted customer email.
    """

    print()
    print("Draft Customer Email")
    print("====================")
    print(result["draft_email"])
    print()


def print_approval_status(result: dict) -> None:
    """
    Print whether the drafted email requires approval.
    """

    print("Approval Status")
    print("===============")

    if result["requires_approval"]:
        print("Requires human approval before sending: YES")
    else:
        print("Requires human approval before sending: NO")

    print()


def main() -> None:
    """
    Main starting point for the command-line version of the prototype.

    This file now mainly handles:
        - asking the user for input
        - calling the reusable workflow
        - printing the result
        - saving the result
    """

    print("Yacht MLS Agent POC")
    print("===================")
    print()
    print("Phase 4: Refactored broker assistant workflow")
    print()

    customer_name = input("Customer name: ").strip()

    if customer_name == "":
        customer_name = "there"

    print()
    print("Enter search filters.")
    print("Press Enter to skip any filter.")
    print()

    max_price = get_optional_int("Maximum price: ")
    min_length = get_optional_int("Minimum length in feet: ")
    max_length = get_optional_int("Maximum length in feet: ")
    location_keyword = get_optional_text("Location keyword: ")
    min_cabins = get_optional_int("Minimum cabins: ")

    print()

    # Run the reusable workflow.
    # This is the core business logic of the prototype.
    result = run_broker_assistant_workflow(
        customer_name=customer_name,
        max_price=max_price,
        min_length=min_length,
        max_length=max_length,
        location_keyword=location_keyword,
        min_cabins=min_cabins,
    )

    # Print the workflow result in readable sections.
    print_search_criteria(result)
    print_matched_yachts(result)
    print_email_draft(result)
    print_approval_status(result)

    # Save the full structured result as JSON.
    output_path = save_agent_run(result)

    print("Structured Output")
    print("=================")
    print(f"Saved result to: {output_path}")


if __name__ == "__main__":
    main()