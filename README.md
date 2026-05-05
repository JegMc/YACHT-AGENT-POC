# Yacht MLS Agent POC

This is a standalone proof of concept for a yacht MLS assistant.

The goal is to demonstrate how an AI agent could eventually help brokers, customers, or internal staff retrieve yacht listing information and draft customer-facing responses.

## Current Status

Phase 1 is a non-AI prototype.

It can:

- Load mock yacht listing data from a JSON file
- Search listings by price, length, location, and cabins
- Print matching yacht summaries in the terminal

## Current Project Structure

```text
YACHT-AGENT-POC/
  data/
    yachts.json
  tools/
    __init__.py
    yacht_search.py
  main.py
  README.md