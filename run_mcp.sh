#!/bin/bash

# 1. Move to the project directory
cd /home/afzal/projects/financial-mcp-server

# 2. Log that we started (for debugging)
echo "Starting MCP Server at $(date)" >> /tmp/mcp_debug.log

# 3. Run the server using UV
# We use full path to UV and redirect 'stderr' (errors) to our log file
/home/afzal/.local/bin/uv run --quiet server.py 2>> /tmp/mcp_debug.log