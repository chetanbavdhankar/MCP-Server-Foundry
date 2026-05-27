import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

@pytest.fixture(scope="session", autouse=True)
def test_datasets_env():
    """Create a temporary directory for synthetic datasets and mock the environment variable."""
    temp_dir = tempfile.mkdtemp(prefix="mcp_test_datasets_")
    orig_env = os.environ.get("DATASETS_DIR")
    os.environ["DATASETS_DIR"] = temp_dir

    # Create synthetic test datasets
    # 1. Standard sales CSV (numeric and categorical)
    df_sales = pd.DataFrame({
        "id": range(1, 11),
        "product": ["Apple", "Orange", "Banana", "Apple", "Apple", "Banana", "Orange", "Apple", "Apple", "Pear"],
        "price": [1.2, 0.8, 0.5, 1.2, 1.2, 0.5, 0.8, 1.2, 1.2, 2.5],
        "quantity": [10, 20, 15, 8, 12, 5, 25, 14, 10, 3],
        "category": ["fruit", "fruit", "fruit", "fruit", "fruit", "fruit", "fruit", "fruit", "fruit", "fruit"],
        "notes": ["fresh", "sweet", "ripe", "fresh", "fresh", None, "sweet", "fresh", "fresh", "rare"]
    })
    df_sales.to_csv(Path(temp_dir) / "sales.csv", index=False)

    # 2. Financial Excel file
    df_finance = pd.DataFrame({
        "account": ["A1", "A2", "A1", "A3", "A2"],
        "amount": [1000, 2500, -300, 500, 150],
        "status": ["active", "active", "pending", "closed", "active"]
    })
    df_finance.to_excel(Path(temp_dir) / "finance.xlsx", index=False)

    # 3. Simple JSON dataset
    df_users = pd.DataFrame({
        "username": ["bob", "alice", "charlie"],
        "age": [32, 25, 41],
        "role": ["admin", "user", "user"]
    })
    df_users.to_json(Path(temp_dir) / "users.json", orient="records")

    # 4. Dataset with duplicates, missing values, outliers for Quality testing in JSON format
    import json
    quality_data = [
        {"val": 10.0, "mixed": "a"},
        {"val": 12.0, "mixed": "b"},
        {"val": 11.5, "mixed": 123},
        {"val": 10.0, "mixed": "c"},
        {"val": 12.0, "mixed": "d"},
        {"val": None, "mixed": "e"},
        {"val": 100.0, "mixed": "f"},
        {"val": 11.0, "mixed": "g"},
        {"val": 9.5, "mixed": "h"},
        {"val": 10.5, "mixed": "i"}
    ]
    with open(Path(temp_dir) / "quality.json", "w") as f:
        json.dump(quality_data, f)

    # 5. Empty dataset
    df_empty = pd.DataFrame(columns=["col1", "col2"])
    df_empty.to_csv(Path(temp_dir) / "empty.csv", index=False)

    yield Path(temp_dir)

    # Cleanup
    shutil.rmtree(temp_dir)
    if orig_env is not None:
        os.environ["DATASETS_DIR"] = orig_env
    else:
        del os.environ["DATASETS_DIR"]
