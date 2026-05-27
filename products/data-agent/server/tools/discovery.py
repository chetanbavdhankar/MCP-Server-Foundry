from typing import Literal, List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from backends import dataset_cache, clean_record
from discovery import scan_datasets, get_dataset_filepath

# Input Pydantic models
class DescribeDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")

class PreviewDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")
    n: int = Field(default=10, description="Number of rows to preview")
    mode: Literal["head", "tail", "random"] = Field(default="head", description="Mode of preview: head, tail, or random")

def list_datasets() -> List[Dict[str, Any]]:
    """List all available datasets in the configured directory, including file metadata."""
    return scan_datasets()

def describe_dataset(args: DescribeDatasetInput) -> Dict[str, Any]:
    """Describe a dataset's columns including data types, nullability, unique count, and sample values."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    columns_desc = []
    for col in df.columns:
        series = df[col]
        sample_vals = series.dropna().unique()[:5].tolist()
        sample_vals = [clean_record({"val": v})["val"] for v in sample_vals]
        
        columns_desc.append({
            "name": str(col),
            "dtype": str(series.dtype),
            "nullable": bool(series.isnull().any()),
            "unique_count": int(series.nunique()),
            "sample_values": sample_vals
        })
        
    return {"columns": columns_desc}

def preview_dataset(args: PreviewDatasetInput) -> List[Dict[str, Any]]:
    """Preview records from a dataset using head, tail, or random selection modes."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    n = min(max(args.n, 1), len(df)) if len(df) > 0 else 0
    if n == 0:
        return []
        
    if args.mode == "head":
        sub_df = df.head(n)
    elif args.mode == "tail":
        sub_df = df.tail(n)
    else: # random
        sub_df = df.sample(n)
        
    records = sub_df.to_dict(orient="records")
    return [clean_record(r) for r in records]

def register_discovery_tools(mcp: FastMCP):
    """Register discovery tools to the FastMCP server instance."""
    mcp.tool(name="list_datasets")(list_datasets)
    mcp.tool(name="describe_dataset")(describe_dataset)
    mcp.tool(name="preview_dataset")(preview_dataset)
