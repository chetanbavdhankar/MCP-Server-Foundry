"""
OpenAPI specification parsing utilities.

This module provides functions for loading, validating, and normalizing
OpenAPI specifications in YAML or JSON format.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ParsedEndpoint:
    """Represents a parsed API endpoint from the OpenAPI spec."""
    
    path: str
    method: str
    operation_id: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]
    tags: List[str]
    security: List[Dict[str, Any]]


@dataclass
class ParsedSpec:
    """Normalized representation of an OpenAPI specification."""
    
    title: str
    version: str
    description: str
    servers: List[Dict[str, str]]
    endpoints: List[ParsedEndpoint]
    schemas: Dict[str, Any]
    security_schemes: Dict[str, Any]
    raw_spec: Dict[str, Any]


class SpecParserError(Exception):
    """Exception raised when spec parsing fails."""
    pass


def load_spec(spec_path: str) -> Dict[str, Any]:
    """
    Load an OpenAPI specification from a file.
    
    Args:
        spec_path: Path to the OpenAPI spec file (YAML or JSON)
        
    Returns:
        Parsed specification as a dictionary
        
    Raises:
        SpecParserError: If file cannot be loaded or parsed
    """
    path = Path(spec_path)
    
    if not path.exists():
        raise SpecParserError(f"Spec file not found: {spec_path}")
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif path.suffix == '.json':
                return json.load(f)
            else:
                raise SpecParserError(f"Unsupported file format: {path.suffix}")
    except yaml.YAMLError as e:
        raise SpecParserError(f"YAML parsing error: {str(e)}")
    except json.JSONDecodeError as e:
        raise SpecParserError(f"JSON parsing error: {str(e)}")
    except Exception as e:
        raise SpecParserError(f"Error loading spec: {str(e)}")


def validate_spec(spec: Dict[str, Any]) -> None:
    """
    Validate that the spec contains required OpenAPI fields.
    
    Args:
        spec: The loaded specification dictionary
        
    Raises:
        SpecParserError: If required fields are missing
    """
    required_fields = ['openapi', 'info', 'paths']
    missing = [field for field in required_fields if field not in spec]
    
    if missing:
        raise SpecParserError(f"Missing required fields: {', '.join(missing)}")
    
    if not spec['openapi'].startswith('3.'):
        raise SpecParserError(f"Unsupported OpenAPI version: {spec['openapi']}")
    
    if 'title' not in spec['info']:
        raise SpecParserError("Missing required field: info.title")


def parse_endpoint(path: str, method: str, operation: Dict[str, Any], 
                   spec: Dict[str, Any]) -> ParsedEndpoint:
    """
    Parse a single endpoint from the OpenAPI spec.
    
    Args:
        path: The endpoint path
        method: HTTP method (get, post, etc.)
        operation: The operation object from the spec
        spec: The full spec for resolving references
        
    Returns:
        ParsedEndpoint object
    """
    return ParsedEndpoint(
        path=path,
        method=method.upper(),
        operation_id=operation.get('operationId', f"{method}_{path.replace('/', '_')}"),
        summary=operation.get('summary', ''),
        description=operation.get('description', ''),
        parameters=operation.get('parameters', []),
        request_body=operation.get('requestBody'),
        responses=operation.get('responses', {}),
        tags=operation.get('tags', []),
        security=operation.get('security', spec.get('security', []))
    )


def normalize_spec(spec: Dict[str, Any]) -> ParsedSpec:
    """
    Normalize an OpenAPI spec into a structured format.
    
    Args:
        spec: The loaded OpenAPI specification
        
    Returns:
        ParsedSpec object with normalized data
        
    Raises:
        SpecParserError: If spec cannot be normalized
    """
    validate_spec(spec)
    
    info = spec['info']
    endpoints = []
    
    # Parse all endpoints
    for path, path_item in spec.get('paths', {}).items():
        for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
            if method in path_item:
                try:
                    endpoint = parse_endpoint(path, method, path_item[method], spec)
                    endpoints.append(endpoint)
                except Exception as e:
                    # Log but don't fail on individual endpoint parsing errors
                    print(f"Warning: Failed to parse {method.upper()} {path}: {str(e)}")
    
    return ParsedSpec(
        title=info.get('title', 'Untitled API'),
        version=info.get('version', '1.0.0'),
        description=info.get('description', ''),
        servers=spec.get('servers', [{'url': 'http://localhost'}]),
        endpoints=endpoints,
        schemas=spec.get('components', {}).get('schemas', {}),
        security_schemes=spec.get('components', {}).get('securitySchemes', {}),
        raw_spec=spec
    )


def extract_auth_requirements(spec: ParsedSpec) -> Dict[str, Any]:
    """
    Extract authentication requirements from the spec.
    
    Args:
        spec: Normalized specification
        
    Returns:
        Dictionary describing auth requirements
    """
    auth_info = {
        "schemes": {},
        "required": False,
        "env_vars": []
    }
    
    for scheme_name, scheme_def in spec.security_schemes.items():
        auth_type = scheme_def.get('type', 'unknown')
        auth_info["schemes"][scheme_name] = {
            "type": auth_type,
            "description": scheme_def.get('description', ''),
        }
        
        # Determine environment variable names
        if auth_type == 'apiKey':
            auth_info["env_vars"].append(f"API_KEY")
            auth_info["required"] = True
        elif auth_type == 'http':
            auth_info["env_vars"].append(f"API_TOKEN")
            auth_info["required"] = True
        elif auth_type == 'oauth2':
            auth_info["env_vars"].append(f"OAUTH_CLIENT_ID")
            auth_info["env_vars"].append(f"OAUTH_CLIENT_SECRET")
            auth_info["required"] = True
    
    return auth_info

# Made with Bob
