import os
import math
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Any, List

class DatasetCache:
    """LRU Cache for Pandas DataFrames with automatic file modification time validation."""
    def __init__(self, maxsize: int = 32):
        self.maxsize = maxsize
        self.cache: Dict[str, Tuple[float, pd.DataFrame]] = {} # path -> (mtime, dataframe)
        self.access_order: List[str] = []

    def get_dataset(self, path: str) -> pd.DataFrame:
        """Get dataset from cache or load it if not cached or file has changed."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset file not found: {path}")

        mtime = os.path.getmtime(path)

        if path in self.cache:
            cached_mtime, df = self.cache[path]
            if cached_mtime == mtime:
                # Cache hit: update LRU access order
                self.access_order.remove(path)
                self.access_order.append(path)
                return df
            else:
                # Invalidate stale cache entry
                del self.cache[path]
                self.access_order.remove(path)

        # Cache miss: load from file
        df = self._load_file(path)

        # Evict LRU item if maxsize exceeded
        if len(self.cache) >= self.maxsize:
            evict_path = self.access_order.pop(0)
            del self.cache[evict_path]

        self.cache[path] = (mtime, df)
        self.access_order.append(path)
        return df

    def _load_file(self, path: str) -> pd.DataFrame:
        """Load dataset based on file extension."""
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == '.csv':
                return pd.read_csv(path)
            elif ext in ('.xlsx', '.xls'):
                return pd.read_excel(path)
            elif ext == '.json':
                # Try reading as standard pandas json (record-oriented or custom)
                try:
                    return pd.read_json(path)
                except Exception:
                    # Fallback for other JSON formats (e.g. array of flat dicts)
                    import json
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return pd.DataFrame(data)
                    elif isinstance(data, dict) and "records" in data:
                        return pd.DataFrame(data["records"])
                    else:
                        return pd.DataFrame([data])
            elif ext == '.parquet':
                return pd.read_parquet(path)
            else:
                raise ValueError(f"Unsupported file format: {ext}")
        except Exception as e:
            raise ValueError(f"Failed to load dataset file at {path}: {str(e)}")

# Global Cache Instance
dataset_cache = DatasetCache(maxsize=32)

def sanitize_for_json(val: Any) -> Any:
    """Coerce value to be JSON-serializable (converts NaN to None, datetime to string)."""
    if pd.isna(val):
        return None
    elif isinstance(val, (float, int)):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(val, (pd.Timestamp, np.datetime64)):
        return val.isoformat() if hasattr(val, 'isoformat') else str(val)
    elif hasattr(val, 'item'):  # numpy types
        item_val = val.item()
        if isinstance(item_val, float) and (math.isnan(item_val) or math.isinf(item_val)):
            return None
        return item_val
    elif isinstance(val, dict):
        return {k: sanitize_for_json(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_for_json(v) for v in val]
    return val

def clean_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Clean all dictionary values to guarantee JSON serialization."""
    return {col: sanitize_for_json(val) for col, val in row.items()}
