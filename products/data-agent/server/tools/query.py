from typing import Literal, List, Dict, Any, Optional
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from backends import dataset_cache, clean_record
from discovery import get_dataset_filepath

class WhereClause(BaseModel):
    model_config = ConfigDict(extra="forbid")
    col: str = Field(description="Column name to apply filter on")
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "regex", "is_null"] = Field(description="Comparison operator")
    value: Any = Field(default=None, description="Filter value (ignored if operator is is_null)")

class FilterRowsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    where: List[WhereClause] = Field(default_factory=list, description="List of filter clauses")
    columns: Optional[List[str]] = Field(default=None, description="Optional subset of columns to return")
    limit: int = Field(default=100, ge=1, description="Maximum number of rows to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

class CountRowsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    where: List[WhereClause] = Field(default_factory=list, description="List of filter clauses")

class DistinctValuesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    column: str = Field(description="Column name to calculate distinct values for")
    where: List[WhereClause] = Field(default_factory=list, description="List of filter clauses")
    limit: int = Field(default=50, ge=1, description="Maximum number of unique values to return")

def apply_filters(df: pd.DataFrame, where: List[WhereClause]) -> pd.DataFrame:
    """Helper to apply WhereClause filters dynamically to a DataFrame."""
    if df.empty or not where:
        return df
        
    mask = pd.Series(True, index=df.index)
    for clause in where:
        col = clause.col
        if col not in df.columns:
            raise ValueError(f"Column '{col}' does not exist in the dataset")
            
        op = clause.op
        val = clause.value
        series = df[col]
        
        if op == "eq":
            mask &= (series == val)
        elif op == "ne":
            mask &= (series != val)
        elif op == "gt":
            mask &= (series > val)
        elif op == "gte":
            mask &= (series >= val)
        elif op == "lt":
            mask &= (series < val)
        elif op == "lte":
            mask &= (series <= val)
        elif op == "in":
            if not isinstance(val, list):
                val = [val]
            mask &= series.isin(val)
        elif op == "contains":
            mask &= series.astype(str).str.contains(str(val), case=False, na=False)
        elif op == "regex":
            mask &= series.astype(str).str.contains(str(val), regex=True, na=False)
        elif op == "is_null":
            mask &= series.isnull()
        else:
            raise ValueError(f"Unsupported operator: {op}")
            
    return df[mask]

def filter_rows(args: FilterRowsInput) -> Dict[str, Any]:
    """Filter and retrieve rows from a dataset based on dynamic comparison criteria."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    filtered_df = apply_filters(df, args.where)
    total_matched = len(filtered_df)
    
    # Apply projection
    if args.columns:
        # Validate columns
        missing = [c for c in args.columns if c not in filtered_df.columns]
        if missing:
            raise ValueError(f"Columns not found in dataset: {missing}")
        proj_df = filtered_df[args.columns]
    else:
        proj_df = filtered_df
        
    # Apply pagination
    sliced_df = proj_df.iloc[args.offset : args.offset + args.limit]
    
    records = sliced_df.to_dict(orient="records")
    returned_records = [clean_record(r) for r in records]
    
    return {
        "total_matched": total_matched,
        "returned": len(returned_records),
        "rows": returned_records
    }

def count_rows(args: CountRowsInput) -> Dict[str, int]:
    """Count the number of rows matching the query criteria."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    filtered_df = apply_filters(df, args.where)
    return {"count": len(filtered_df)}

def distinct_values(args: DistinctValuesInput) -> List[Dict[str, Any]]:
    """Get distinct values and their frequency in a column, filtered by matching criteria."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    filtered_df = apply_filters(df, args.where)
    if args.column not in filtered_df.columns:
        raise ValueError(f"Column '{args.column}' does not exist in dataset")
        
    counts = filtered_df[args.column].value_counts(dropna=False)
    results = []
    for val, freq in counts.head(args.limit).items():
        results.append({
            "value": clean_record({"v": val})["v"],
            "frequency": int(freq)
        })
        
    return results

def register_query_tools(mcp: FastMCP):
    """Register query tools to the FastMCP server instance."""
    mcp.tool(name="filter_rows")(filter_rows)
    mcp.tool(name="count_rows")(count_rows)
    mcp.tool(name="distinct_values")(distinct_values)
