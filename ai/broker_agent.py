# ai/broker_agent.py

"""
Tool-calling yacht broker agent.

This file is the main AI agent workflow for the POC.

Flow:
1. Receive a natural-language customer request.
2. Let the model call the local search_yachts tool.
3. Run the local Python search function.
4. Give the search results back to the model.
5. Ask the model for structured broker output.
6. Build a safer customer-facing email draft from the structured result.

Important rule:
- Listing IDs can exist in backend JSON for the app/developer.
- Listing IDs should NOT appear in draft_customer_email.
"""

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from tools.yacht_search import search_yachts


load_dotenv()

client = OpenAI()


SEARCH_YACHTS_TOOL = {
    "type": "function",
    "name": "search_yachts",
    "description": (
        "Search mock yacht MLS listings using hard filters and soft preferences. "
        "Use this whenever the user asks for yacht recommendations, available options, "
        "or matching listings. Always include the original customer request in "
        "customer_request so the tool can detect words like near, around, sporty, modern, "
        "family-friendly, or weekend trips."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "customer_request": {
                "type": "string",
                "description": "The original customer request exactly as written.",
            },
            "max_price": {
                "type": ["integer", "null"],
                "description": "Maximum yacht price in dollars, or null if not specified.",
            },
            "min_length": {
                "type": ["integer", "null"],
                "description": "Minimum yacht length in feet, or null if not specified.",
            },
            "max_length": {
                "type": ["integer", "null"],
                "description": "Maximum yacht length in feet, or null if not specified.",
            },
            "target_length": {
                "type": ["integer", "null"],
                "description": (
                    "Approximate target yacht length in feet. "
                    "Example: use 60 for 'around 60 feet'. Use null if not specified."
                ),
            },
            "location_keyword": {
                "type": ["string", "null"],
                "description": (
                    "Single location keyword such as Florida, Miami, Fort Lauderdale, "
                    "Palm Beach, Newport, or null."
                ),
            },
            "location_keywords": {
                "type": ["array", "null"],
                "description": (
                    "Multiple location keywords if the request mentions more than one place, "
                    "such as ['Miami', 'Palm Beach']. Use null if not needed."
                ),
                "items": {"type": "string"},
            },
            "location_flexibility": {
                "type": ["string", "null"],
                "description": (
                    "Use 'exact' for exact location requests, 'nearby_ok' when the user says "
                    "near/around/preferably near, and 'statewide_ok' for broad Florida searches. "
                    "Use null if unclear."
                ),
            },
            "min_cabins": {
                "type": ["integer", "null"],
                "description": "Minimum number of cabins, or null if not specified.",
            },
            "soft_preferences": {
                "type": ["array", "null"],
                "description": (
                    "Descriptive preferences such as ['sporty', 'modern'], "
                    "['family-friendly'], ['weekend trips'], or null."
                ),
                "items": {"type": "string"},
            },
        },
        "required": [
            "customer_request",
            "max_price",
            "min_length",
            "max_length",
            "target_length",
            "location_keyword",
            "location_keywords",
            "location_flexibility",
            "min_cabins",
            "soft_preferences",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}


def _run_search_yachts_tool(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Execute the local Python search_yachts function using model-provided arguments.

    The model does not run this function directly.
    Our Python code receives the requested arguments and runs the real function.
    """
    return search_yachts(
        max_price=arguments.get("max_price"),
        min_length=arguments.get("min_length"),
        max_length=arguments.get("max_length"),
        target_length=arguments.get("target_length"),
        location_keyword=arguments.get("location_keyword"),
        location_keywords=arguments.get("location_keywords"),
        location_flexibility=arguments.get("location_flexibility"),
        min_cabins=arguments.get("min_cabins"),
        soft_preferences=arguments.get("soft_preferences"),
        customer_request=arguments.get("customer_request"),
    )


def _format_money(value: int | None) -> str:
    """
    Format money for customer-facing text.
    """
    if value is None:
        return "price available on request"

    return f"${value:,}"


def _sanitize_customer_email(email_text: str, raw_tool_results: list[dict[str, Any]]) -> str:
    """
    Remove internal-looking listing IDs from customer-facing email text.

    The backend JSON can keep IDs.
    The customer email should not expose them.
    """
    cleaned = email_text or ""

    for yacht in raw_tool_results:
        yacht_id = str(yacht.get("id", "")).strip()

        if yacht_id:
            cleaned = cleaned.replace(yacht_id, "")

    patterns = [
        r"\(?(?:listing\s*)?(?:id|yacht id|boat id)\s*[:#]?\s*[A-Za-z]?\d+\)?",
        r"\bY\d{3,}\b",
        r"\bID\s*[:#]\s*\b",
    ]

    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" +\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _build_safe_customer_email(final_result: dict[str, Any], raw_tool_results: list[dict[str, Any]]) -> str:
    """
    Build a safer customer-facing email from the structured result.

    This intentionally ignores listing IDs.
    It uses names, prices, lengths, locations, cabins, and plain-English reasons.
    """
    customer_profile = final_result.get("customer_profile", {})
    customer_name = customer_profile.get("name") or "there"
    matched_yachts = final_result.get("matched_yachts", [])
    follow_up_questions = final_result.get("follow_up_questions", [])

    has_relaxed_alternatives = any(
        yacht.get("_match_type") == "relaxed_alternative"
        for yacht in raw_tool_results
    )

    lines: list[str] = [
        f"Hi {customer_name},",
        "",
        "Thank you for sharing what you are looking for.",
    ]

    if not matched_yachts:
        lines.extend(
            [
                "",
                "I was not able to identify a strong match from the current available listings based on the details provided.",
                "The most useful next step would be to confirm a few search details so I can narrow this down properly.",
            ]
        )

    elif has_relaxed_alternatives:
        lines.extend(
            [
                "",
                "I did not find an exact match for every part of the request, but I found a few close alternatives that may still be worth reviewing.",
                "",
                "Close options:",
            ]
        )

    else:
        lines.extend(
            [
                "",
                "I found a few options that appear to fit the search criteria and may be worth reviewing.",
                "",
                "Recommended options:",
            ]
        )

    for yacht in matched_yachts[:3]:
        name = yacht.get("name", "Unnamed yacht")
        price = _format_money(yacht.get("price"))
        length_ft = yacht.get("length_ft")
        location = yacht.get("location", "location not specified")
        cabins = yacht.get("cabins")
        reason = yacht.get("reason", "").strip()
        tradeoffs = yacht.get("tradeoffs", "").strip()

        summary = f"- {name}: {length_ft} ft, {cabins} cabins, located in {location}, listed at {price}."

        lines.append(summary)

        if reason:
            lines.append(f"  Why it may fit: {reason}")

        if tradeoffs and tradeoffs.lower() not in ["none", "n/a", "no major tradeoffs"]:
            lines.append(f"  Note: {tradeoffs}")

    if follow_up_questions:
        lines.extend(
            [
                "",
                "Before moving forward, I would suggest confirming:",
            ]
        )

        for question in follow_up_questions[:3]:
            lines.append(f"- {question}")

    lines.extend(
        [
            "",
            "I can review these options with you and narrow the list based on your priorities.",
            "",
            "Best,",
            "Your Yacht Broker",
        ]
    )

    return _sanitize_customer_email("\n".join(lines), raw_tool_results)


def _build_no_tool_response(customer_request: str) -> dict[str, Any]:
    """
    Return a safe fallback response if the model does not call the yacht search tool.
    """
    return {
        "request_summary": "The request could not be processed through the yacht search tool.",
        "search_interpretation": {
            "hard_filters": {
                "max_price": None,
                "min_length": None,
                "max_length": None,
                "target_length": None,
                "location_keywords": [],
                "min_cabins": None,
            },
            "soft_preferences": [],
            "missing_information": [
                "Budget",
                "Length range",
                "Location",
                "Cabin requirement",
            ],
            "timing_context": None,
            "location_flexibility": None,
            "no_exact_match": True,
        },
        "customer_profile": {
            "name": None,
            "budget": None,
            "location_preference": None,
            "size_preference": None,
            "cabin_preference": None,
            "intended_use": None,
        },
        "matched_yachts": [],
        "broker_notes": [
            "The model did not call the search_yachts tool.",
            "Try making the request more direct, such as: 'Find yachts under $1.5M in Miami and Palm Beach between 45 and 60 feet.'",
        ],
        "follow_up_questions": [
            "What is the customer's budget?",
            "What yacht length range is the customer considering?",
            "What location should the search focus on?",
            "How many cabins does the customer need?",
        ],
        "draft_customer_email": (
            "Hi there,\n\n"
            "Thank you for sharing what you are looking for. "
            "I need a few more details before I can make useful recommendations.\n\n"
            "Could you confirm your preferred budget, size range, location, and cabin requirements?\n\n"
            "Best,\n"
            "Your Yacht Broker"
        ),
        "requires_approval": True,
        "approval_reason": "No customer-facing email should be sent until the broker reviews the request and search results.",
        "status": "needs_broker_review",
        "original_customer_request": customer_request,
        "used_tool_calling": False,
        "tool_calls_used": [],
        "raw_tool_results": [],
    }


def run_broker_agent(customer_request: str) -> dict[str, Any]:
    """
    Run a tool-calling yacht broker agent.
    """
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    instructions = """
You are a yacht broker assistant for a SaaS MLS proof of concept.

Your job:
- Help brokers respond to customer yacht search requests.
- Use the search_yachts tool whenever the user asks for yacht recommendations, available options, or matching listings.
- Do not invent yacht listings. Only recommend yachts returned by the search_yachts tool.
- If the request is vague, still use the tool with the filters you can identify and use null for missing hard filters.
- Separate hard filters from soft preferences.
- Treat words like sporty, modern, family-friendly, entertaining, weekend trips, and low hours as soft preferences.
- Treat price, length, location, and cabin count as hard filters.
- For wording like "near", "around", or "preferably near", use location_flexibility = nearby_ok.
- For wording like "around 60 feet", use target_length = 60 instead of forcing an exact 60-foot match.
- If the tool returns relaxed alternatives, clearly say there was no exact match and explain what filters may need to change.
- Include practical broker notes and follow-up questions.
- Draft customer-facing text only as a draft.
- Do not claim that an email has been sent.
- Always require human approval before sending customer-facing text.
- Be honest about missing information and limitations.

Customer-facing email rules:
- Do not include backend IDs, yacht IDs, boat IDs, listing IDs, raw JSON, tool metadata, or internal fields.
- Listing IDs may appear in backend JSON, but not inside draft_customer_email.
"""

    input_list: list[Any] = [
        {
            "role": "user",
            "content": customer_request,
        }
    ]

    first_response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_list,
        tools=[SEARCH_YACHTS_TOOL],
    )

    input_list.extend(first_response.output)

    tool_calls_used: list[dict[str, Any]] = []
    raw_tool_results: list[dict[str, Any]] = []

    for item in first_response.output:
        if item.type == "function_call" and item.name == "search_yachts":
            arguments = json.loads(item.arguments)

            if not arguments.get("customer_request"):
                arguments["customer_request"] = customer_request

            tool_result = _run_search_yachts_tool(arguments)

            tool_calls_used.append(
                {
                    "tool_name": item.name,
                    "arguments": arguments,
                    "matched_count": len(tool_result),
                }
            )

            raw_tool_results = tool_result

            input_list.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(tool_result),
                }
            )

    if not tool_calls_used:
        return _build_no_tool_response(customer_request)

    final_response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_list,
        tools=[SEARCH_YACHTS_TOOL],
        text={
            "format": {
                "type": "json_schema",
                "name": "EnhancedBrokerAgentResponse",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "request_summary": {
                            "type": "string",
                            "description": "A short plain-English summary of what the customer is looking for.",
                        },
                        "search_interpretation": {
                            "type": "object",
                            "description": "How the agent interpreted the search request.",
                            "properties": {
                                "hard_filters": {
                                    "type": "object",
                                    "properties": {
                                        "max_price": {
                                            "type": ["integer", "null"],
                                            "description": "Maximum price in dollars.",
                                        },
                                        "min_length": {
                                            "type": ["integer", "null"],
                                            "description": "Minimum length in feet.",
                                        },
                                        "max_length": {
                                            "type": ["integer", "null"],
                                            "description": "Maximum length in feet.",
                                        },
                                        "target_length": {
                                            "type": ["integer", "null"],
                                            "description": "Approximate target length in feet.",
                                        },
                                        "location_keywords": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Locations mentioned in the request.",
                                        },
                                        "min_cabins": {
                                            "type": ["integer", "null"],
                                            "description": "Minimum cabin requirement.",
                                        },
                                    },
                                    "required": [
                                        "max_price",
                                        "min_length",
                                        "max_length",
                                        "target_length",
                                        "location_keywords",
                                        "min_cabins",
                                    ],
                                    "additionalProperties": False,
                                },
                                "soft_preferences": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Style or lifestyle preferences such as sporty, modern, family-friendly, or weekend trips.",
                                },
                                "missing_information": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Important missing details the broker should confirm.",
                                },
                                "timing_context": {
                                    "type": ["string", "null"],
                                    "description": "Timing details such as next weekend, if mentioned.",
                                },
                                "location_flexibility": {
                                    "type": ["string", "null"],
                                    "description": "Whether the location was exact, nearby_ok, statewide_ok, or unclear.",
                                },
                                "no_exact_match": {
                                    "type": "boolean",
                                    "description": "True if the returned options are close alternatives instead of exact matches.",
                                },
                            },
                            "required": [
                                "hard_filters",
                                "soft_preferences",
                                "missing_information",
                                "timing_context",
                                "location_flexibility",
                                "no_exact_match",
                            ],
                            "additionalProperties": False,
                        },
                        "customer_profile": {
                            "type": "object",
                            "description": "Customer preferences extracted or inferred from the request.",
                            "properties": {
                                "name": {
                                    "type": ["string", "null"],
                                    "description": "Customer name if mentioned.",
                                },
                                "budget": {
                                    "type": ["integer", "null"],
                                    "description": "Customer budget in dollars if mentioned.",
                                },
                                "location_preference": {
                                    "type": ["string", "null"],
                                    "description": "Preferred yacht location or region.",
                                },
                                "size_preference": {
                                    "type": ["string", "null"],
                                    "description": "Preferred yacht size or size range.",
                                },
                                "cabin_preference": {
                                    "type": ["string", "null"],
                                    "description": "Preferred number of cabins.",
                                },
                                "intended_use": {
                                    "type": ["string", "null"],
                                    "description": "Intended use such as family cruising, entertaining, long-range cruising, or day trips.",
                                },
                            },
                            "required": [
                                "name",
                                "budget",
                                "location_preference",
                                "size_preference",
                                "cabin_preference",
                                "intended_use",
                            ],
                            "additionalProperties": False,
                        },
                        "matched_yachts": {
                            "type": "array",
                            "description": "Yachts recommended to the customer based only on tool results.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {
                                        "type": "string",
                                        "description": "Internal yacht listing ID. This can appear in JSON but must not appear in draft_customer_email.",
                                    },
                                    "name": {
                                        "type": "string",
                                        "description": "Yacht name.",
                                    },
                                    "price": {
                                        "type": "integer",
                                        "description": "Yacht price in dollars.",
                                    },
                                    "length_ft": {
                                        "type": "integer",
                                        "description": "Yacht length in feet.",
                                    },
                                    "location": {
                                        "type": "string",
                                        "description": "Yacht location.",
                                    },
                                    "cabins": {
                                        "type": "integer",
                                        "description": "Number of cabins.",
                                    },
                                    "match_score": {
                                        "type": "number",
                                        "description": "A rough fit score from 0 to 1 based on the customer request.",
                                    },
                                    "reason": {
                                        "type": "string",
                                        "description": "Why this yacht fits the customer's request.",
                                    },
                                    "tradeoffs": {
                                        "type": "string",
                                        "description": "Any limitations or tradeoffs for this yacht.",
                                    },
                                },
                                "required": [
                                    "id",
                                    "name",
                                    "price",
                                    "length_ft",
                                    "location",
                                    "cabins",
                                    "match_score",
                                    "reason",
                                    "tradeoffs",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "broker_notes": {
                            "type": "array",
                            "description": "Internal notes for the broker.",
                            "items": {"type": "string"},
                        },
                        "follow_up_questions": {
                            "type": "array",
                            "description": "Questions the broker should ask the customer before moving forward.",
                            "items": {"type": "string"},
                        },
                        "draft_customer_email": {
                            "type": "string",
                            "description": "Customer-facing email draft. Must not include listing IDs, backend IDs, raw JSON, or tool metadata.",
                        },
                        "requires_approval": {
                            "type": "boolean",
                            "description": "Whether a human broker must approve before sending.",
                        },
                        "approval_reason": {
                            "type": "string",
                            "description": "Why human approval is required.",
                        },
                        "status": {
                            "type": "string",
                            "description": "Workflow status such as pending_broker_review or needs_more_information.",
                        },
                    },
                    "required": [
                        "request_summary",
                        "search_interpretation",
                        "customer_profile",
                        "matched_yachts",
                        "broker_notes",
                        "follow_up_questions",
                        "draft_customer_email",
                        "requires_approval",
                        "approval_reason",
                        "status",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    final_result = json.loads(final_response.output_text)

    safe_email = _build_safe_customer_email(
        final_result=final_result,
        raw_tool_results=raw_tool_results,
    )

    final_result["draft_customer_email"] = safe_email
    final_result["requires_approval"] = True

    if "approval" not in final_result.get("approval_reason", "").lower():
        final_result["approval_reason"] = (
            "A human broker must review the recommendations and customer-facing draft before anything is sent."
        )

    final_result["original_customer_request"] = customer_request
    final_result["used_tool_calling"] = True
    final_result["tool_calls_used"] = tool_calls_used
    final_result["raw_tool_results"] = raw_tool_results

    return final_result