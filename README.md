# Yacht MLS Agent POC

This is a standalone proof of concept for a yacht MLS assistant.

The goal is to demonstrate how an AI agent could eventually help brokers, customers, or internal staff retrieve yacht listing information and draft customer-facing responses.

## Current Project Structure

```text
YACHT-AGENT-POC/
  ai/
    __init__.py
    request_parser.py
  api/
    __init__.py
    server.py
  data/
    yachts.json
  outputs/
    latest_agent_run.json
  tools/
    __init__.py
    yacht_search.py
    email_drafting.py
    output_writer.py
  workflows/
    __init__.py
    broker_assistant.py
  .env
  .env.example
  .gitignore
  main.py
  README.md
  requirements.txt
