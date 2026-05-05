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
        # With strict schemas, we list all possible fields as required.
        # Nullable fields can still be null when the user did not specify them.
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

    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    instructions = """
    You are a yacht broker assistant for a SaaS MLS proof of concept.

    Your job:
    - Help brokers respond to customer yacht search requests.
    - Use the search_yachts tool when the user asks for yacht options.
    - After tool results are available, recommend relevant matches.
    - Draft a customer-facing email.
    - Do not claim that an email has been sent.
    - Always require human approval before sending customer-facing text.
    """

    # This is the first model request.
    # The model can either answer directly or request a tool call.
    input_list = [
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

    # Add the model's first output to the conversation.
    # If the model requested a function call, that function call is in first_response.output.
    input_list += first_response.output

    tool_calls_used = []
    raw_tool_results = []

    # Look through the model output for function/tool calls.
    for item in first_response.output:
        if item.type == "function_call" and item.name == "search_yachts":
            # The model sends tool arguments as a JSON string.
            arguments = json.loads(item.arguments)

            # Run the actual local Python tool.
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

    # If no tool was used, return a clear response instead of failing silently.
    if not tool_calls_used:
        return {
            "original_customer_request": customer_request,
            "used_tool_calling": False,
            "tool_calls_used": [],
            "matched_yachts": [],
            "broker_notes": [
                "The model did not call the search_yachts tool for this request."
            ],
            "draft_customer_email": "",
            "requires_approval": True,
            "status": "needs_review",
        }

    # This second model request asks the model to use the tool result
    # and produce a final structured response.
    final_response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_list,
        tools=[SEARCH_YACHTS_TOOL],
        text={
            "format": {
                "type": "json_schema",
                "name": "BrokerAgentResponse",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "matched_yachts": {
                            "type": "array",
                            "description": "Yachts recommended to the customer.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "price": {"type": "integer"},
                                    "length_ft": {"type": "integer"},
                                    "location": {"type": "string"},
                                    "cabins": {"type": "integer"},
                                    "reason": {
                                        "type": "string",
                                        "description": "Why this yacht fits the request.",
                                    },
                                },
                                "required": [
                                    "id",
                                    "name",
                                    "price",
                                    "length_ft",
                                    "location",
                                    "cabins",
                                    "reason",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "broker_notes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Internal notes for the broker.",
                        },
                        "draft_customer_email": {
                            "type": "string",
                            "description": "Customer-facing email draft.",
                        },
                        "requires_approval": {
                            "type": "boolean",
                            "description": "Whether a human must approve before sending.",
                        },
                        "status": {
                            "type": "string",
                            "description": "Workflow status.",
                        },
                    },
                    "required": [
                        "matched_yachts",
                        "broker_notes",
                        "draft_customer_email",
                        "requires_approval",
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