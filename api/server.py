# FastAPI is the framework we use to create a local API.
from fastapi import FastAPI

# BaseModel lets us define the expected shape of incoming JSON data.
from pydantic import BaseModel

# Import the AI request parser.
from ai.request_parser import parse_yacht_request

# Import the reusable broker assistant workflow we already built.
from workflows.broker_assistant import run_broker_assistant_workflow

from ai.broker_agent import run_broker_agent

# Create the FastAPI application.
app = FastAPI(
    title="Yacht MLS Agent POC API",
    description="A local API for testing the yacht broker assistant workflow.",
    version="0.2.0",
)


class BrokerAssistantRequest(BaseModel):
    """
    Defines the JSON request body for the manual broker assistant endpoint.

    This endpoint expects already-structured search filters.
    """

    customer_name: str = "there"
    max_price: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    location_keyword: str | None = None
    min_cabins: int | None = None


class NaturalLanguageBrokerAssistantRequest(BaseModel):
    """
    Defines the JSON request body for the AI-powered endpoint.

    This endpoint accepts a normal English request.
    """

    customer_request: str


class BrokerAgentRequest(BaseModel):
    """
    Defines the JSON request body for the tool-calling broker agent endpoint.
    """

    customer_request: str

@app.get("/")
def read_root() -> dict:
    """
    Simple test endpoint.

    If this works, the API server is running.
    """

    return {
    "message": "Yacht MLS Agent POC API is running.",
    "manual_endpoint": "POST /broker-assistant/run",
    "ai_parser_endpoint": "POST /broker-assistant/run-natural-language",
    "tool_calling_agent_endpoint": "POST /broker-agent/run",
}


@app.post("/broker-assistant/run")
def run_broker_assistant(request: BrokerAssistantRequest) -> dict:
    """
    Run the broker assistant workflow from structured JSON filters.

    This is the non-AI endpoint.
    """

    result = run_broker_assistant_workflow(
        customer_name=request.customer_name,
        max_price=request.max_price,
        min_length=request.min_length,
        max_length=request.max_length,
        location_keyword=request.location_keyword,
        min_cabins=request.min_cabins,
    )

    return result


@app.post("/broker-assistant/run-natural-language")
def run_broker_assistant_from_natural_language(
    request: NaturalLanguageBrokerAssistantRequest,
) -> dict:
    """
    Run the broker assistant workflow from a natural-language request.

    Flow:
        1. User sends a normal English request.
        2. AI extracts structured search filters.
        3. Existing broker workflow runs with those filters.
        4. API returns the full structured result.
    """

    # Use AI to turn the natural-language request into structured filters.
    parsed_filters = parse_yacht_request(request.customer_request)

    # Use the parsed customer name if it exists.
    # Otherwise, fall back to a generic greeting.
    customer_name = parsed_filters["customer_name"] or "there"

    # Run the same reusable workflow as the manual endpoint.
    result = run_broker_assistant_workflow(
        customer_name=customer_name,
        max_price=parsed_filters["max_price"],
        min_length=parsed_filters["min_length"],
        max_length=parsed_filters["max_length"],
        location_keyword=parsed_filters["location_keyword"],
        min_cabins=parsed_filters["min_cabins"],
    )

    # Add AI-specific metadata to the response.
    result["original_customer_request"] = request.customer_request
    result["ai_parsed_filters"] = parsed_filters
    result["used_ai_parser"] = True

    return result


@app.post("/broker-agent/run")
def run_tool_calling_broker_agent(request: BrokerAgentRequest) -> dict:
    """
    Run the tool-calling broker agent.

    Flow:
        1. Receive a natural-language customer request.
        2. Let the model decide how to call the search_yachts tool.
        3. Run the local Python search_yachts function.
        4. Send the tool result back to the model.
        5. Return a structured broker/customer response.
    """

    result = run_broker_agent(request.customer_request)

    return result