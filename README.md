# MCP Server Foundry

Welcome to the **MCP Server Foundry**, a premier workspace hosting production-grade integrations and gateways between Model Context Protocol (MCP) clients and heterogeneous data systems. 

This repository decouples REST API gateways from physical data search pipelines, exposing two specialized products designed to fulfill diverse agentic integration requirements out-of-the-box.

## Products

### 📊 [Product A: Data Agent (Stable)](products/data-agent/README.md)
A high-performance, dataset-agnostic FastMCP server that lets AI agents directly "talk to your data." Supports lazy-loading, automatic LRU cache invalidation (up to 32 slots), and rich analytical aggregations over local **CSV, Excel, JSON, and Parquet** files. Includes a strict read-only SQL escape hatch sandboxed in memory-only DuckDB connections with robust syntax tree validation.

### 🔌 [Product B: API Foundry (Alpha)](products/api-foundry/README.md)
An automated compiler that converts any **OpenAPI 3.0+ REST specification** into a complete, structured-logged, and Pydantic-validated FastMCP stdio server in seconds. Automatically maps security schemes to environment variables and handles asynchronous HTTP traffic cleanly using `httpx.AsyncClient`.

***

## Web UI Dashboard
A cyberpunk-themed, glassmorphic visual dashboard orchestrator is available to inspect files, execute ReAct agent analytic sessions, and preview tool execution traces dynamically.

### Setup and Launch UI
```bash
# Install dependencies
pip install -r requirements.txt

# Run Web UI
python foundry_ui.py
```
Open your browser at `http://localhost:7777` to get started immediately!

***

- To explore the long-term vision, defensive moats, and business plans, check out [VISION.md](VISION.md).
- To view recent changes and migration notes, check out [CHANGELOG.md](CHANGELOG.md).

## Recent Changes

### Product Decoupling & Modernization
- **Why:** The repository previously conflated an OpenAPI-to-MCP generator and a local dataset chatbot into a single, confusing structure. We split these into distinct, specialized products to simplify maintenance, enhance security, and scale development independently.
- **How:** Reorganized into `/products/data-agent` and `/products/api-foundry`. Integrated `FastMCP` dynamically as the underlying protocol layer for both, utilizing a global `DatasetCache` (32 slots) for Product A and a programmatic `datamodel-code-generator` schema builder for Product B.
- **Impact:** Eliminates codebase cross-contamination, speeds up tool discovery, and introduces 100% type safety via strict Pydantic models.

### End-to-End JSON-RPC Verification
- **Why:** To guarantee that generated REST-to-MCP servers strictly comply with the MCP protocol specification and cleanly handle invalid parameters at the network boundaries rather than crashing standard clients.
- **How:** Implemented a new integration test in `products/api-foundry/foundry/tests/test_e2e_petstore.py` that compiles the Petstore OpenAPI specification, spawns the server as an async subprocess via `asyncio.create_subprocess_exec`, executes the JSON-RPC initialization handshake over stdio, and asserts that calling a tool with malformed `arguments` throws the standard `-32602` error.
- **Impact:** Ensures robust validation before request execution, guaranteeing production stability and zero hanging test processes.