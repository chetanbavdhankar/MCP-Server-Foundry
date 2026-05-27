import logging
import json
import os
import re
import time
from typing import Any, Dict

SECRET_PATTERNS = re.compile(r'(key|token|secret|password|auth|credential|api[-_]?key)', re.IGNORECASE)

def sanitize_value(key: str, value: Any) -> Any:
    """Mask sensitive keys to prevent leakage in logs."""
    if isinstance(value, str) and SECRET_PATTERNS.search(key):
        return "[MASKED]"
    return value

def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively mask sensitive values in a dictionary."""
    sanitized = {}
    for k, v in d.items():
        if isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = sanitize_value(k, v)
    return sanitized

class JsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        if hasattr(record, "extra_fields"):
            log_data.update(sanitize_dict(getattr(record, "extra_fields")))
        return json.dumps(log_data)

def setup_logger(name: str, level: str = "INFO", json_format: bool = True) -> logging.Logger:
    """Set up and return a standardized logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler()
        if json_format:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
