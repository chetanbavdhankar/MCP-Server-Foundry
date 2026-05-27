# Data Agent — Talk-to-your-data MCP Server

A dataset-agnostic, production-grade Model Context Protocol (MCP) server that exposes high-fidelity analytical capabilities over local files (.csv, .xlsx, .xls, .json, .parquet) without code generation.

## Overview
Every data science team ends up hand-rolling custom scripts to let LLMs query internal CSV/Excel datasets, introducing loose validation, severe performance bottlenecks, and security vulnerabilities. 
The **Data Agent** solves this at the source by exposing a standardized, robust FastMCP interface containing comprehensive discovery, query, analytics, and quality diagnostics, with built-in LRU caching and strict read-only SQL sandboxing.

## Architecture
```
    LLM Client (e.g. Chat UI, Claude Desktop)
                  │ (Stdio JSON-RPC)
                  ▼
         ┌──────────────────┐
         │  FastMCP Server  │
         └────────┬─────────┘
                  │ (Lazy-load & Cache)
                  ▼
         ┌──────────────────┐
         │   DatasetCache   │ ◄─── LRU Cache (maxsize=32)
         └────────┬─────────┘      Validates file modification times
                  │
                  ├───► .csv (Pandas)
                  ├───► .xlsx / .xls (OpenPyXL)
                  ├───► .json
                  ├───► .parquet
                  ▼
         ┌──────────────────┐
         │   DuckDB & SQL   │ ◄─── Read-only sandboxing via sqlglot
         └──────────────────┘
```

## Setup Instructions

### Prerequisites
- Python 3.10+
- Pip package manager

### Installation
```bash
cd products/data-agent
pip install -e .
```

### Configuration
Configure the path to your datasets using the `DATASETS_DIR` environment variable:
```bash
# Windows PowerShell
$env:DATASETS_DIR="c:/Users/cheta/Documents/coding/mcp_server/datasets"

# Unix/macOS
export DATASETS_DIR="/path/to/your/datasets"
```

Place any supported data files inside your datasets folder. The server scans this directory at startup and exposes the entire tool suite against all files.

### Launch Server
```bash
python server/main.py
```

## Usage Examples

Every tool accepts a single `args` object parameter.

### 1. Distinct Values
Returns distinct values in a column along with their frequencies.
- **Tool**: `distinct_values`
- **Arguments**:
```json
{
  "args": {
    "dataset": "emails",
    "column": "category",
    "limit": 10
  }
}
```

### 2. Groupby Aggregation
Performs database-style aggregations with WHERE and HAVING filters.
- **Tool**: `aggregate`
- **Arguments**:
```json
{
  "args": {
    "dataset": "emails",
    "group_by": ["category"],
    "metrics": [
      {"col": "id", "fn": "count", "alias": "total_count"}
    ],
    "having": [
      {"col": "total_count", "op": "gt", "value": 5}
    ]
  }
}
```

### 3. Read-Only SQL Escape Hatch
Executes arbitrary read-only queries sandboxed in a memory-only DuckDB instance.
- **Tool**: `sql_query`
- **Arguments**:
```json
{
  "args": {
    "dataset": "emails",
    "sql": "SELECT category, count(*) as count FROM emails GROUP BY category HAVING count > 5"
  }
}
```

## Recent Changes
- **FastMCP Refactor**: Switched from hand-rolled JSON-RPC wrappers to `mcp.server.fastmcp.FastMCP` standard.
- **Dataset-Agnostic Interface**: Replaced per-dataset generation with a single, scanning service utilizing dynamic file adapters.
- **Enhanced Security**: Integrated recursive `sqlglot` AST validation to strictly prevent SQL write queries (`CREATE`, `INSERT`, `DROP`, `COMMAND` etc.).
- **LRU Caching**: Added automatic invalidation of cached datasets upon file system change, backed by a 32-slot LRU queue.

## Technical Debt Log
- **Large Dataset Memory Profiles**: Currently loads the entire dataset into memory for query processing. For mult-gigabyte files, lookups should be pushed entirely to direct on-disk DuckDB tables rather than Pandas loading.
- **Nullable Type Coercions**: Floating-point columns containing NaN are coerced to `None` for serialization, which loses their numeric distinction in pandas.
