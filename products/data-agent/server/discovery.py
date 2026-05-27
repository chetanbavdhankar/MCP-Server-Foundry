import os
import time
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
from backends import dataset_cache

# Configurable datasets directory
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "datasets"

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.json', '.parquet'}

def get_datasets_dir() -> Path:
    """Ensure datasets directory exists and return it dynamically."""
    datasets_dir = Path(os.environ.get("DATASETS_DIR", DEFAULT_DIR))
    if not datasets_dir.exists():
        datasets_dir.mkdir(parents=True, exist_ok=True)
    return datasets_dir

def get_dataset_filepath(dataset_name: str) -> Path:
    """Find the filepath for a given dataset stem in the datasets directory."""
    datasets_dir = get_datasets_dir()
    for ext in SUPPORTED_EXTENSIONS:
        path = datasets_dir / f"{dataset_name}{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Dataset '{dataset_name}' not found inside '{datasets_dir}'")

def scan_datasets() -> List[Dict[str, Any]]:
    """Scan the datasets directory and return metadata for all found files."""
    datasets_dir = get_datasets_dir()
    results = []
    
    for item in datasets_dir.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            name = item.stem
            size_bytes = item.stat().st_size
            modified_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(item.stat().st_mtime))
            fmt = item.suffix[1:].lower()
            
            try:
                df = dataset_cache.get_dataset(str(item))
                rows = len(df)
                columns = len(df.columns)
            except Exception:
                rows = 0
                columns = 0
                
            results.append({
                "name": name,
                "rows": rows,
                "columns": columns,
                "size_bytes": size_bytes,
                "modified_at": modified_at,
                "format": fmt
            })
            
    return results
