# Migration Changelog

This document logs the file reorganization, product decoupling, and modular refactoring of the repository into two distinct, production-grade products: **Data Agent** (Product A) and **API Foundry** (Product B).

## Decoupling & Restructuring (Product Splitting)

The repository was reorganized to separate the talk-to-your-data MCP server and the OpenAPI-to-MCP code generator.

### 1. Product A: Data Agent
Located in `products/data-agent/`. Exposes stable, dataset-agnostic FastMCP tools over local CSV, Excel, JSON, and Parquet files with built-in LRU caching and strict read-only SQL sandboxing.

- **NEW** [`products/data-agent/server/main.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/main.py): Entry point for the FastMCP Data Agent stdio server.
- **NEW** [`products/data-agent/server/backends.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/backends.py): Custom LRU Cache (`maxsize=32`) for Pandas DataFrames with automatic file modification time checks, datatypes coercion, and JSON sanitization.
- **NEW** [`products/data-agent/server/discovery.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/discovery.py): Dynamic filesystem discovery scanner for matching local datasets using a configurable `DATASETS_DIR` environment variable.
- **NEW Modular Tools**:
  - [`tools/discovery.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/tools/discovery.py): Catalog tools (`list_datasets`).
  - [`tools/query.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/tools/query.py): Dataset pagination and row filtering (`filter_rows`, `count_rows`, `distinct_values`).
  - [`tools/analytics.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/tools/analytics.py): Analytical aggregations (`aggregate`, `summary_statistics`, `top_n`).
  - [`tools/quality.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/tools/quality.py): Diagnostics report assessing missing rates, mixed types, and IQR-based outliers (`data_quality_report`).
  - [`tools/sql.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/data-agent/server/tools/sql.py): Sandboxed read-only SQL execution environment via memory-only DuckDB with recursive AST verification using `sqlglot` (`sql_query`).

### 2. Product B: API Foundry
Located in `products/api-foundry/`. A pipeline engine that converts OpenAPI specifications into complete, production-ready FastMCP servers.

- **MOVED** `foundry/` directory to `products/api-foundry/foundry/`
- **MOVED** `templates/` directory to `products/api-foundry/templates/`
- **MOVED** `forge_recipe.py` to `products/api-foundry/forge_recipe.py`
- **MODIFIED** [`products/api-foundry/foundry/core/validation.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/products/api-foundry/foundry/core/validation.py): Modernized schema resolution to use programmatic `datamodel-code-generator` for building robust Pydantic input/output schemas.
- **MODIFIED** Templates:
  - `server_main_secure.py.j2`: Upgraded to output a FastMCP-based secure server with environment-variable authentication mappings, structured logging, and strict Pydantic model parameters.
  - `test_server.py.j2`: Refactored to generate unit tests targeting the generated FastMCP tool actions.

### 3. Web UI Integration
- **MODIFIED** [`foundry_ui.py`](file:///c:/Users/cheta/Documents/coding/mcp_server/foundry_ui.py): Redesigned to point exclusively to the unified dataset-agnostic **Data Agent** server. Spawns the server process *once* on background Flask startup, shares the Stdio connection thread-safely, and processes multi-turn chatbot queries using a visual ReAct loop trace.

### 4. Housekeeping & Archive
- **MOVED** Obsolete scripts, sample outputs, execution logs, and legacy session files to `/archive/` to restore directory cleanliness.
