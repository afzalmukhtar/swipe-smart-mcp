#!/bin/bash

# Navigate to the script's directory (works from anywhere)
cd "$(dirname "$0")"

# Add .local/bin to PATH for uv
export PATH="$HOME/.local/bin:$PATH"

# Run the MCP server using UV
uv run --quiet server.py