from typing import List, Dict, Any
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from backends import dataset_cache, clean_record
from discovery import get_dataset_filepath

class DataQualityReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(description="The dataset identifier (filename stem, no extension)")

def data_quality_report(args: DataQualityReportInput) -> Dict[str, Any]:
    """Generate a comprehensive data quality report assessing missing rates, duplicate rows, type inconsistencies, and suspected IQR outliers."""
    filepath = get_dataset_filepath(args.dataset)
    df = dataset_cache.get_dataset(str(filepath))
    
    total_rows = len(df)
    if total_rows == 0:
        return {
            "missing_rates": {},
            "duplicate_rows": 0,
            "type_inconsistencies": [],
            "suspected_outliers": []
        }
        
    # 1. Missing Rates
    missing_rates = {}
    for col in df.columns:
        missing_count = int(df[col].isnull().sum())
        missing_rates[col] = float(missing_count / total_rows)
        
    # 2. Duplicate Rows
    duplicate_rows = int(df.duplicated().sum())
    
    # 3. Type Inconsistencies (Mixed types in non-null elements)
    type_inconsistencies = []
    for col in df.columns:
        non_null_series = df[col].dropna()
        if len(non_null_series) > 0:
            types = non_null_series.map(type).unique()
            if len(types) > 1:
                type_inconsistencies.append({
                    "column": col,
                    "unique_types": [t.__name__ for t in types]
                })
                
    # 4. Suspected Outliers via IQR (Interquartile Range)
    suspected_outliers = []
    for col in df.columns:
        series = df[col].dropna()
        if pd.api.types.is_numeric_dtype(series) and len(series) > 0:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = series[(series < lower_bound) | (series > upper_bound)]
            if len(outliers) > 0:
                samples = outliers.head(5).tolist()
                suspected_outliers.append({
                    "column": col,
                    "count": len(outliers),
                    "lower_bound": float(lower_bound),
                    "upper_bound": float(upper_bound),
                    "min_outlier": float(outliers.min()),
                    "max_outlier": float(outliers.max()),
                    "sample_values": [clean_record({"v": s})["v"] for s in samples]
                })
                
    return {
        "missing_rates": missing_rates,
        "duplicate_rows": duplicate_rows,
        "type_inconsistencies": type_inconsistencies,
        "suspected_outliers": suspected_outliers
    }

def register_quality_tools(mcp: FastMCP):
    """Register quality tools to the FastMCP server instance."""
    mcp.tool(name="data_quality_report")(data_quality_report)
