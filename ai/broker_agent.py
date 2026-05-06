# json lets us convert between Python dictionaries and JSON strings.
import json

# os lets us read environment variables from the .env file.
import os

# load_dotenv loads the .env file into the Python process.
from dotenv import load_dotenv

# OpenAI is the official Python client.
from openai import OpenAI

# Import the local Python search tool we already built.
from tools.yacht_search import search_yachts


# Load environment variables from .env.
load_dotenv()

# Create the OpenAI client.
# It automatically reads OPENAI_API_KEY from the environment.
client = OpenAI()


# Define the tool the model is allowed to call.
#
# This does not give the model direct database access.
# It only describes a tool name and the arguments the model can request.
SEARCH_YACHTS_TOOL = {
    "type": "function",
    "name": "search_yachts",
    "description": (
        "Search mock yacht MLS listings using filters such as max price, "
        "length range, location, and minimum cabins. Use this when the user "
        "asks for yacht recommendations or available yacht options."
    ),
    "parameters": {
        "type": "object",
        "properties": {
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
            "location_keyword": {
                "type": ["string", "null"],
                "description": "Location keyword such as Florida, Miami, Newport, or null.",
            },
            "min_cabins": {
                "type": ["integer", "null"],
                "description": "Minimum number of cabins, or null if not specified.",
            },
        },
        "required": [
            "max_price",
            "min_length",
            "max_length",
            "location_keyword",
            "min_cabins",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}


def _run_search_yachts_tool(arguments: dict) -> list[dict]:
    """
    Execute the local Python search_yachts function using model-provided arguments.

    The model does not run this function directly.
    Our Python code receives the requested arguments and runs the real function.
    """

    return search_yachts(
        max_price=arguments.get("max_price"),
        min_length=arguments.get("min_length"),
        max_length=arguments.get("max_length"),
        location_keyword=arguments.get("location_keyword"),
        min_cabins=arguments.get("min_cabins"),
    )


def _build_no_tool_response(customer_request: str) -> dict:
    """
    Return a safe fallback response if the model does not call the yacht search tool.
    """

    return {
        "request_summary": "The request could not be processed through the yacht search tool.",
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
            "Try making the request more direct, such as: 'Use the yacht search tool to find yachts under $1.5M in Florida between 45 and 60 feet.'",
        ],
        "follow_up_questions": [
            "What is the customer's budget?",
            "What yacht length range is the customer considering?",
            "What location should the search focus on?",
            "How many cabins does the customer need?",
        ],
        "draft_customer_email": "",
        "requires_approval": True,
        "approval_reason": "No customer-facing email should be sent until the broker reviews the request and search results.",
        "status": "needs_broker_review",
        "original_customer_request": customer_request,
        "used_tool_calling": False,
        "tool_calls_used": [],
        "raw_tool_results": [],
    }


def run_broker_agent(customer_request: str) -> dict:
    """
    Run a simple tool-calling yacht broker agent.

    Flow:
        1. Send the customer request to the model.
        2. Give the model access to the search_yachts tool definition.
        3. If the model requests a tool call, run the local Python tool.
        4. Send the tool result back to the model.
        5. Ask the model to return a structured final response.
    """

    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    instructions = """
    You are a yacht broker assistant for a SaaS MLS proof of concept.

    Your job:
    - Help brokers respond to customer yacht search requests.
    - Use the search_yachts tool whenever the user asks for yacht recommendations, available options, or matching listings.
    - Do not invent yacht listings. Only recommend yachts returned by the search_yachts tool.
    - If the user request is vague, still use the tool with the filters you can identify and use null for missing filters.
    - After tool results are available, create a practical broker-facing response.
    - Include broker notes and follow-up questions.
    - Draft a customer-facing email only as a draft.
    - Do not claim that an email has been sent.
    - Always require human approval before sending customer-facing text.
    - Be honest about missing information and limitations.
    """

    input_list = [
        {
            "role": "user",
            "content": customer_request,
        }
    ]

    # First model call:
    # The model receives the user's request and can choose to call search_yachts.
    first_response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_list,
        tools=[SEARCH_YACHTS_TOOL],
    )

    # Add the model's first output to the conversation.
    input_list += first_response.output

    tool_calls_used = []
    raw_tool_results = []

    # Look through the first response for function/tool calls.
    for item in first_response.output:
        if item.type == "function_call" and item.name == "search_yachts":
            # The model sends tool arguments as a JSON string.
            arguments = json.loads(item.arguments)

            # Run the actual local Python search function.
            tool_result = _run_search_yachts_tool(arguments)

            tool_calls_used.append(
                {
                    "tool_name": item.name,
                    "arguments": arguments,
                    "matched_count": len(tool_result),
                }
            )

            raw_tool_results = tool_result

            # Send the tool result back to the model.
            input_list.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(tool_result),
                }
            )

    # If no tool was used, return a safe fallback response.
    if not tool_calls_used:
        return _build_no_tool_response(customer_request)

    # Second model call:
    # The model now has the yacht search results and must produce a richer structured response.
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
                                        "description": "Yacht listing ID.",
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
                            "items": {
                                "type": "string",
                            },
                        },
                        "follow_up_questions": {
                            "type": "array",
                            "description": "Questions the broker should ask the customer before moving forward.",
                            "items": {
                                "type": "string",
                            },
                        },
                        "draft_customer_email": {
                            "type": "string",
                            "description": "Customer-facing email draft. This must not claim the email was sent.",
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

    # Convert the model's final JSON text into a Python dictionary.
    final_result = json.loads(final_response.output_text)

    # Add useful metadata that comes from our application, not the model.
    final_result["original_customer_request"] = customer_request
    final_result["used_tool_calling"] = True
    final_result["tool_calls_used"] = tool_calls_used
    final_result["raw_tool_results"] = raw_tool_results

    return final_result