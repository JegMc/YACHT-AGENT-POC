def draft_customer_email(
    customer_name: str,
    yachts: list[dict],
    search_summary: str,
) -> str:
    """
    Create a customer-facing email draft based on matching yacht listings.

    This does not send an email.
    It only creates draft text for a broker or employee to review.
    """

    # If no yachts matched the search, create a polite follow-up email.
    if not yachts:
        return (
            f"Hi {customer_name},\n\n"
            "Thank you for sharing what you're looking for. "
            "I reviewed the available yacht listings, but I was not able to find "
            "a strong match based on the current search criteria.\n\n"
            "I would be happy to broaden the search by adjusting the budget, "
            "location, size range, or cabin requirements.\n\n"
            "Best,\n"
            "Your Yacht Broker"
        )

    # Start the email with a greeting and short introduction.
    email_lines = [
        f"Hi {customer_name},",
        "",
        "Thank you for sharing what you're looking for. "
        "I reviewed the available listings and found a few yachts that may be a good fit.",
        "",
        f"Search summary: {search_summary}",
        "",
        "Recommended options:",
        "",
    ]

    # Add each matching yacht to the email.
    for yacht in yachts:
        email_lines.append(
            f"- {yacht['name']} ({yacht['year']} {yacht['builder']}): "
            f"{yacht['length_ft']} ft, {yacht['cabins']} cabins, "
            f"located in {yacht['location']}, listed at ${yacht['price']:,}."
        )

    # Add a closing paragraph.
    email_lines.extend(
        [
            "",
            "Each of these options appears to align with the search criteria, "
            "but I would recommend reviewing the details together to determine "
            "which yacht best fits your preferences.",
            "",
            "Please let me know if you would like more information on any of these listings.",
            "",
            "Best,",
            "Your Yacht Broker",
        ]
    )

    # Join all email lines into one formatted text block.
    return "\n".join(email_lines)