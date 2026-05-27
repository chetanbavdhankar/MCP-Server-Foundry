from typing import List, Dict, Any
import pandas as pd
import duckdb
import sqlglot
from sqlglot import exp
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from backends import dataset_cache, clean_record
from discovery import get_dataset_filepath

class SQLQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    sql: str = Field(description="Strictly read-only SELECT or WITH SQL statement against the dataset registered as a table of the same name")

def is_query_read_only(sql: str) -> bool:
    """Parse and validate SQL query is strictly a single, read-only SELECT/WITH query."""
    try:
        # Ensure it parses successfully
        statements = sqlglot.parse(sql)
        if len(statements) != 1:
            return False
            
        stmt = statements[0]
        
        # Define forbidden mutating syntax nodes dynamically to prevent version-specific AttributeErrors
        mutating_names = ["Insert", "Delete", "Update", "Drop", "Create", "Alter", "Command", "Execute", "Load", "Merge"]
        mutating_nodes = tuple(getattr(exp, name) for name in mutating_names if hasattr(exp, name))
        
        # Recursively search for any mutating or command execution nodes
        for node in stmt.walk():
            if isinstance(node, mutating_nodes):
                return False
                
        # Check that it contains a SELECT or WITH expression somewhere
        has_select = False
        for node in stmt.walk():
            if isinstance(node, (exp.Select, exp.CTE)):
                has_select = True
                break
                
        return has_select
    except Exception:
        return False

def sql_query(args: SQLQueryInput) -> List[Dict[str, Any]]:
    """Execute a read-only DuckDB SQL query against the dataset registered as a local table/view of the same name."""
    # 1. Enforce Read-Only Security check
    if not is_query_read_only(args.sql):
        raise ValueError("SQL query rejected. Only single, read-only SELECT or WITH queries are allowed.")
        
    # 2. Get dataset
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    # 3. fresh DuckDB connection
    conn = duckdb.connect(database=':memory:')
    try:
        # Register dataframe as a temporary view matching dataset name
        conn.register(args.dataset, df)
        
        # Execute query and get result dataframe
        res_df = conn.execute(args.sql).df()
        
        records = res_df.to_dict(orient="records")
        return [clean_record(r) for r in records]
    except Exception as e:
        raise ValueError(f"SQL execution error: {str(e)}")
    finally:
        conn.close()

def register_sql_tools(mcp: FastMCP):
    """Register SQL tools to the FastMCP server instance."""
    mcp.tool(name="sql_query")(sql_query)
