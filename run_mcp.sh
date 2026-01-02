#!/bin/bash

# Navigate to the script's directory (works from anywhere)
cd "$(dirname "$0")"

# Run the MCP server using UV
uv run --quiet server.py