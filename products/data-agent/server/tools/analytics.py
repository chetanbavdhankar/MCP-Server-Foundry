from typing import Literal, List, Dict, Any, Optional
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from backends import dataset_cache, clean_record
from discovery import get_dataset_filepath
from tools.query import WhereClause, apply_filters

class MetricConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    col: str = Field(description="Column name to aggregate")
    fn: Literal["sum", "mean", "median", "min", "max", "count", "std", "var", "nunique"] = Field(description="Aggregation function")
    alias: Optional[str] = Field(default=None, description="Optional custom name for the aggregated column")

class HavingClause(BaseModel):
    model_config = ConfigDict(extra="forbid")
    col: str = Field(description="Column name (or alias) of the metric to filter on")
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "regex", "is_null"] = Field(description="Comparison operator")
    value: Any = Field(default=None, description="Filter value (ignored if operator is is_null)")

class AggregateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    group_by: List[str] = Field(description="Columns to group by")
    metrics: List[MetricConfig] = Field(description="Metrics to calculate")
    where: List[WhereClause] = Field(default_factory=list, description="Filters to apply BEFORE grouping")
    having: List[HavingClause] = Field(default_factory=list, description="Filters to apply AFTER grouping")
    limit: int = Field(default=100, ge=1, description="Maximum number of grouped rows to return")

class SummaryStatisticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    columns: Optional[List[str]] = Field(default=None, description="Subset of columns to describe")
    where: List[WhereClause] = Field(default_factory=list, description="Filters to apply before describing")

class TopNInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    by: str = Field(description="Column to sort by")
    n: int = Field(default=10, ge=1, description="Number of rows to return")
    ascending: bool = Field(default=False, description="Sort ascending (True) or descending (False)")
    where: List[WhereClause] = Field(default_factory=list, description="Filters to apply before sorting")

def apply_having_filters(df: pd.DataFrame, having: List[HavingClause]) -> pd.DataFrame:
    """Apply HavingClause filters to aggregated DataFrame."""
    if df.empty or not having:
        return df
        
    mask = pd.Series(True, index=df.index)
    for clause in having:
        col = clause.col
        if col not in df.columns:
            raise ValueError(f"Having column '{col}' does not exist in aggregated schema")
            
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

def aggregate(args: AggregateInput) -> List[Dict[str, Any]]:
    """Perform GROUP BY aggregations with metrics, optionally filtered by WHERE and HAVING clauses."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    # 1. Apply where filters
    filtered_df = apply_filters(df, args.where)
    if filtered_df.empty:
        return []
        
    # Validate group_by columns
    for col in args.group_by:
        if col not in filtered_df.columns:
            raise ValueError(f"Group by column '{col}' does not exist in dataset")
            
    # 2. Build aggregation dict
    agg_kwargs = {}
    for m in args.metrics:
        if m.col not in filtered_df.columns:
            raise ValueError(f"Metric column '{m.col}' does not exist in dataset")
        alias = m.alias or f"{m.col}_{m.fn}"
        agg_kwargs[alias] = pd.NamedAgg(column=m.col, aggfunc=m.fn)
        
    # 3. Perform aggregation
    grouped_df = filtered_df.groupby(args.group_by, dropna=False).agg(**agg_kwargs).reset_index()
    
    # 4. Apply having filters
    result_df = apply_having_filters(grouped_df, args.having)
    
    # 5. Apply limit
    limited_df = result_df.head(args.limit)
    
    records = limited_df.to_dict(orient="records")
    return [clean_record(r) for r in records]

def summary_statistics(args: SummaryStatisticsInput) -> Dict[str, Dict[str, Any]]:
    """Calculate per-column summary statistics including count, mean, std, min, percentiles, max, and missing rate."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    filtered_df = apply_filters(df, args.where)
    if filtered_df.empty:
        return {}
        
    cols = args.columns or filtered_df.columns.tolist()
    stats_out = {}
    
    for col in cols:
        if col not in filtered_df.columns:
            raise ValueError(f"Column '{col}' does not exist in dataset")
            
        series = filtered_df[col]
        total_count = len(series)
        missing_count = int(series.isnull().sum())
        missing_rate = missing_count / total_count if total_count > 0 else 0.0
        
        col_stats = {
            "count": int(series.dropna().count()),
            "missing_rate": float(missing_rate)
        }
        
        # If numeric, calculate full descriptive stats
        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            col_stats.update({
                "mean": float(desc.get("mean")) if pd.notna(desc.get("mean")) else None,
                "std": float(desc.get("std")) if pd.notna(desc.get("std")) else None,
                "min": float(desc.get("min")) if pd.notna(desc.get("min")) else None,
                "p25": float(desc.get("25%")) if pd.notna(desc.get("25%")) else None,
                "p50": float(desc.get("50%")) if pd.notna(desc.get("50%")) else None,
                "p75": float(desc.get("75%")) if pd.notna(desc.get("75%")) else None,
                "max": float(desc.get("max")) if pd.notna(desc.get("max")) else None,
            })
        else:
            col_stats.update({
                "mean": None, "std": None, "min": None,
                "p25": None, "p50": None, "p75": None, "max": None
            })
            
        stats_out[col] = clean_record(col_stats)
        
    return stats_out

def top_n(args: TopNInput) -> List[Dict[str, Any]]:
    """Retrieve top N or bottom N rows sorted by a specified column."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    filtered_df = apply_filters(df, args.where)
    if filtered_df.empty:
        return []
        
    if args.by not in filtered_df.columns:
        raise ValueError(f"Sort column '{args.by}' does not exist in dataset")
        
    sorted_df = filtered_df.sort_values(by=args.by, ascending=args.ascending)
    limited_df = sorted_df.head(args.n)
    
    records = limited_df.to_dict(orient="records")
    return [clean_record(r) for r in records]

def register_analytics_tools(mcp: FastMCP):
    """Register analytics tools to the FastMCP server instance."""
    mcp.tool(name="aggregate")(aggregate)
    mcp.tool(name="summary_statistics")(summary_statistics)
    mcp.tool(name="top_n")(top_n)
