# json lets us convert the model's JSON text response into a Python dictionary.
import json

# os lets us read environment variables like OPENAI_MODEL.
import os

# load_dotenv loads variables from the .env file into the Python process.
from dotenv import load_dotenv

# OpenAI is the official Python client for calling OpenAI models.
from openai import OpenAI


# Load environment variables from .env.
load_dotenv()


# Create the OpenAI client.
# It automatically looks for OPENAI_API_KEY in the environment.
client = OpenAI()


def parse_yacht_request(customer_request: str) -> dict:
    """
    Use AI to extract structured yacht search filters from natural language.

    This is used by the /broker-assistant/run-natural-language endpoint.
    """

    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    instructions = """
    You extract yacht search filters from customer or broker requests.

    Rules:
    - Return only structured JSON that matches the schema.
    - Convert prices like "$1.5M" or "1.5 million" into integers like 1500000.
    - Convert feet ranges like "45-60 ft" into min_length and max_length.
    - If a value is not mentioned, use null.
    - If no customer name is mentioned, use null for customer_name.
    - Use "Florida" if the request says Florida, FL, Miami, Fort Lauderdale, Palm Beach, Tampa, or Naples.
    - Do not invent filters that are not in the request.
    """

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=customer_request,
        text={
            "format": {
                "type": "json_schema",
                "name": "YachtSearchFilters",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "customer_name": {
                            "type": ["string", "null"],
                            "description": "The customer's first name if mentioned."
                        },
                        "max_price": {
                            "type": ["integer", "null"],
                            "description": "Maximum yacht price in dollars."
                        },
                        "min_length": {
                            "type": ["integer", "null"],
                            "description": "Minimum yacht length in feet."
                        },
                        "max_length": {
                            "type": ["integer", "null"],
                            "description": "Maximum yacht length in feet."
                        },
                        "location_keyword": {
                            "type": ["string", "null"],
                            "description": "Location keyword such as Florida, Miami, or Newport."
                        },
                        "min_cabins": {
                            "type": ["integer", "null"],
                            "description": "Minimum number of cabins."
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0 to 1."
                        },
                        "missing_info": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Important missing details, if any."
                        }
                    },
                    "required": [
                        "customer_name",
                        "max_price",
                        "min_length",
                        "max_length",
                        "location_keyword",
                        "min_cabins",
                        "confidence",
                        "missing_info"
                    ],
                    "additionalProperties": False
                }
            }
        },
    )

    parsed_filters = json.loads(response.output_text)

    return parsed_filters