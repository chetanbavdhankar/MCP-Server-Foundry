import sys
import os
from mcp.server.fastmcp import FastMCP

# Ensure server path is in sys.path for local module resolution
server_dir = os.path.dirname(os.path.abspath(__file__))
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from tools.discovery import register_discovery_tools
from tools.query import register_query_tools
from tools.analytics import register_analytics_tools
from tools.quality import register_quality_tools
from tools.sql import register_sql_tools

# Initialize FastMCP Server
mcp = FastMCP("Data Agent")

# Register tool groups
register_discovery_tools(mcp)
register_query_tools(mcp)
register_analytics_tools(mcp)
register_quality_tools(mcp)
register_sql_tools(mcp)

if __name__ == "__main__":
    # Start the FastMCP stdio server
    mcp.run()
