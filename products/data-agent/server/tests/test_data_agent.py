import pytest
import os
from pydantic import ValidationError
from mcp.server.fastmcp import FastMCP

# Add server directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.discovery import list_datasets, describe_dataset, preview_dataset, DescribeDatasetInput, PreviewDatasetInput
from tools.query import filter_rows, count_rows, distinct_values, FilterRowsInput, CountRowsInput, DistinctValuesInput, WhereClause
from tools.analytics import aggregate, summary_statistics, top_n, AggregateInput, SummaryStatisticsInput, TopNInput, MetricConfig, HavingClause
from tools.quality import data_quality_report, DataQualityReportInput
from tools.sql import sql_query, SQLQueryInput

# Map tool names to functions for test compatibility
_TOOL_MAP = {
    "list_datasets": list_datasets,
    "describe_dataset": describe_dataset,
    "preview_dataset": preview_dataset,
    "filter_rows": filter_rows,
    "count_rows": count_rows,
    "distinct_values": distinct_values,
    "aggregate": aggregate,
    "summary_statistics": summary_statistics,
    "top_n": top_n,
    "data_quality_report": data_quality_report,
    "sql_query": sql_query,
}

def get_tool(name: str):
    if name not in _TOOL_MAP:
        raise ValueError(f"Tool {name} not found")
    return _TOOL_MAP[name]

def test_list_datasets(test_datasets_env):
    """Test list_datasets returns all synthetic datasets."""
    list_tool = get_tool("list_datasets")
    res = list_tool()
    
    names = [d["name"] for d in res]
    assert "sales" in names
    assert "finance" in names
    assert "users" in names
    assert "quality" in names
    assert "empty" in names
    
    # Assert fields in metadata
    sales_meta = [d for d in res if d["name"] == "sales"][0]
    assert sales_meta["rows"] == 10
    assert sales_meta["columns"] == 6
    assert sales_meta["format"] == "csv"

def test_describe_dataset():
    """Test describe_dataset returns correct column details."""
    describe_tool = get_tool("describe_dataset")
    args = DescribeDatasetInput(dataset="sales")
    res = describe_tool(args)
    
    cols = res["columns"]
    col_names = [c["name"] for c in cols]
    assert "product" in col_names
    assert "price" in col_names
    assert "quantity" in col_names
    
    price_col = [c for c in cols if c["name"] == "price"][0]
    assert price_col["dtype"] in ("float64", "float32")
    assert price_col["nullable"] is False
    assert price_col["unique_count"] == 4

def test_preview_dataset():
    """Test preview_dataset options (head, tail, random)."""
    preview_tool = get_tool("preview_dataset")
    
    # 1. Head
    args = PreviewDatasetInput(dataset="sales", n=3, mode="head")
    res = preview_tool(args)
    assert len(res) == 3
    assert res[0]["id"] == 1
    
    # 2. Tail
    args = PreviewDatasetInput(dataset="sales", n=2, mode="tail")
    res = preview_tool(args)
    assert len(res) == 2
    assert res[-1]["id"] == 10
    
    # 3. Empty dataset edge case
    args = PreviewDatasetInput(dataset="empty", n=5, mode="head")
    res = preview_tool(args)
    assert len(res) == 0

def test_filter_rows():
    """Test filter_rows with diverse where clauses (eq, gt, contains, is_null)."""
    filter_tool = get_tool("filter_rows")
    
    # Filter: product == Apple
    where = [WhereClause(col="product", op="eq", value="Apple")]
    args = FilterRowsInput(dataset="sales", where=where, limit=100)
    res = filter_tool(args)
    assert res["total_matched"] == 5
    assert all(r["product"] == "Apple" for r in res["rows"])
    
    # Filter: quantity > 10
    where = [WhereClause(col="quantity", op="gt", value=10)]
    args = FilterRowsInput(dataset="sales", where=where, limit=100)
    res = filter_tool(args)
    assert res["total_matched"] == 5
    
    # Filter: notes is_null
    where = [WhereClause(col="notes", op="is_null")]
    args = FilterRowsInput(dataset="sales", where=where, limit=100)
    res = filter_tool(args)
    assert res["total_matched"] == 1
    
    # Filter: notes contains "ripe"
    where = [WhereClause(col="notes", op="contains", value="ripe")]
    args = FilterRowsInput(dataset="sales", where=where, limit=100)
    res = filter_tool(args)
    assert res["total_matched"] == 1
    assert res["rows"][0]["product"] == "Banana"

def test_count_rows():
    """Test count_rows counts correctly with filters."""
    count_tool = get_tool("count_rows")
    where = [WhereClause(col="product", op="eq", value="Apple")]
    args = CountRowsInput(dataset="sales", where=where)
    res = count_tool(args)
    assert res["count"] == 5

def test_distinct_values():
    """Test distinct_values returns unique value counts."""
    distinct_tool = get_tool("distinct_values")
    args = DistinctValuesInput(dataset="sales", column="product")
    res = distinct_tool(args)
    
    assert len(res) == 4
    products = {r["value"]: r["frequency"] for r in res}
    assert products["Apple"] == 5
    assert products["Orange"] == 2
    assert products["Banana"] == 2
    assert products["Pear"] == 1

def test_aggregate():
    """Test groupby aggregates with pre-filters and post-filters."""
    agg_tool = get_tool("aggregate")
    
    # SELECT product, sum(quantity) as tot_qty, mean(price) as avg_price GROUP BY product HAVING tot_qty > 10
    args = AggregateInput(
        dataset="sales",
        group_by=["product"],
        metrics=[
            MetricConfig(col="quantity", fn="sum", alias="tot_qty"),
            MetricConfig(col="price", fn="mean", alias="avg_price")
        ],
        having=[
            HavingClause(col="tot_qty", op="gt", value=10)
        ]
    )
    res = agg_tool(args)
    assert len(res) == 3 # Apple, Orange, Banana (not Pear)
    
    apple_row = [r for r in res if r["product"] == "Apple"][0]
    assert apple_row["tot_qty"] == 54 # 10+8+12+14+10 = 54
    assert abs(apple_row["avg_price"] - 1.2) < 0.01

def test_summary_statistics():
    """Test summary_statistics on numeric vs categorical columns."""
    stats_tool = get_tool("summary_statistics")
    args = SummaryStatisticsInput(dataset="sales", columns=["price", "product"])
    res = stats_tool(args)
    
    assert "price" in res
    assert "product" in res
    
    price_stats = res["price"]
    assert price_stats["count"] == 10
    assert price_stats["min"] == 0.5
    assert price_stats["max"] == 2.5
    assert abs(price_stats["mean"] - 1.11) < 0.01
    
    product_stats = res["product"]
    assert product_stats["count"] == 10
    assert product_stats["mean"] is None # non-numeric

def test_top_n():
    """Test top_n returns highest or lowest rows."""
    top_tool = get_tool("top_n")
    args = TopNInput(dataset="sales", by="quantity", n=3, ascending=False)
    res = top_tool(args)
    
    assert len(res) == 3
    assert res[0]["quantity"] == 25 # largest
    assert res[1]["quantity"] == 20
    assert res[2]["quantity"] == 15

def test_data_quality_report():
    """Test data_quality_report detects missingness, mixed types, and outliers via IQR."""
    quality_tool = get_tool("data_quality_report")
    args = DataQualityReportInput(dataset="quality")
    res = quality_tool(args)
    
    # 1. Missingness
    assert res["missing_rates"]["val"] == 0.1 # 1 out of 10 is missing (None)
    assert res["missing_rates"]["mixed"] == 0.0
    
    # 2. Type Inconsistencies
    assert len(res["type_inconsistencies"]) == 1
    assert res["type_inconsistencies"][0]["column"] == "mixed"
    assert "str" in res["type_inconsistencies"][0]["unique_types"]
    assert "int" in res["type_inconsistencies"][0]["unique_types"]
    
    # 3. IQR Outliers
    assert len(res["suspected_outliers"]) == 1
    assert res["suspected_outliers"][0]["column"] == "val"
    assert res["suspected_outliers"][0]["count"] == 1
    assert res["suspected_outliers"][0]["min_outlier"] == 100.0

def test_sql_query_happy_path():
    """Test that sql_query runs successfully on SELECT and WITH statements."""
    sql_tool = get_tool("sql_query")
    
    # SELECT query
    args = SQLQueryInput(dataset="sales", sql="SELECT product, count(*) as cnt FROM sales GROUP BY product ORDER BY cnt DESC")
    res = sql_tool(args)
    assert len(res) == 4
    assert res[0]["product"] == "Apple"
    assert res[0]["cnt"] == 5
    
    # WITH query
    sql_with = """
    WITH filtered AS (
        SELECT * FROM sales WHERE price > 1.0
    )
    SELECT sum(quantity) as total_q FROM filtered
    """
    args = SQLQueryInput(dataset="sales", sql=sql_with)
    res = sql_tool(args)
    assert res[0]["total_q"] == 57 # 10 + 8 + 12 + 14 + 10 (Apple) + 3 (Pear) = 57

def test_sql_query_sandboxing_security():
    """Test that sql_query rejects write statements, command executions, and stacked statements."""
    sql_tool = get_tool("sql_query")
    
    # 1. Stacked queries (multi-statement)
    with pytest.raises(ValueError, match="SQL query rejected"):
        sql_tool(SQLQueryInput(dataset="sales", sql="SELECT * FROM sales; SELECT * FROM sales"))
        
    # 2. INSERT statement
    with pytest.raises(ValueError, match="SQL query rejected"):
        sql_tool(SQLQueryInput(dataset="sales", sql="INSERT INTO sales VALUES (11, 'Banana', 0.5, 10, 'fruit', 'test')"))
        
    # 3. DELETE statement
    with pytest.raises(ValueError, match="SQL query rejected"):
        sql_tool(SQLQueryInput(dataset="sales", sql="DELETE FROM sales WHERE id = 1"))
        
    # 4. DROP statement
    with pytest.raises(ValueError, match="SQL query rejected"):
        sql_tool(SQLQueryInput(dataset="sales", sql="DROP TABLE sales"))
        
    # 5. CREATE statement
    with pytest.raises(ValueError, match="SQL query rejected"):
        sql_tool(SQLQueryInput(dataset="sales", sql="CREATE TABLE bad_table (id INT)"))

def test_extra_fields_forbidden():
    """Test that passing extra fields in validation models throws ValidationError."""
    with pytest.raises(ValidationError):
        # Pass unknown field "extra_key" to DescribeDatasetInput
        DescribeDatasetInput(dataset="sales", extra_key="invalid")
        
    with pytest.raises(ValidationError):
        # Pass unknown field to WhereClause
        WhereClause(col="product", op="eq", value="Apple", extra_key=123)
