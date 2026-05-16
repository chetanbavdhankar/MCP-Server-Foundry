"""
Security utilities for secret detection and input sanitization.

This module provides functions to detect secrets in OpenAPI specs,
externalize them to environment variables, and sanitize user inputs
to prevent injection attacks.
"""

import re
import html
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SecretLocation:
    """Represents a detected secret in the spec."""
    path: str  # JSON path to the secret
    field_name: str
    secret_type: str  # 'api_key', 'token', 'password', etc.
    value: Optional[str] = None  # Only for detection, never stored


class SecretDetector:
    """
    Detects secrets and credentials in OpenAPI specifications.
    
    Identifies API keys, tokens, passwords, and other sensitive data
    that should be externalized to environment variables.
    """
    
    # Patterns that indicate a field contains a secret
    SECRET_FIELD_PATTERNS = [
        r'api[_-]?key',
        r'apikey',
        r'token',
        r'secret',
        r'password',
        r'passwd',
        r'credential',
        r'auth',
        r'bearer',
        r'access[_-]?key',
        r'private[_-]?key',
        r'client[_-]?secret',
    ]
    
    # Patterns that indicate a value is a secret
    SECRET_VALUE_PATTERNS = [
        r'^sk-[a-zA-Z0-9]{32,}$',  # OpenAI-style keys
        r'^[A-Za-z0-9_-]{32,}$',  # Generic long alphanumeric
        r'^ghp_[a-zA-Z0-9]{36}$',  # GitHub personal access token
        r'^gho_[a-zA-Z0-9]{36}$',  # GitHub OAuth token
    ]
    
    def __init__(self):
        self.detected_secrets: List[SecretLocation] = []
    
    def detect_secrets_in_spec(self, spec_data: Dict[str, Any]) -> List[SecretLocation]:
        """
        Scan OpenAPI spec for secrets and credentials.
        
        Args:
            spec_data: Parsed OpenAPI specification
            
        Returns:
            List of detected secret locations
        """
        self.detected_secrets = []
        
        # Check security schemes
        if "components" in spec_data and "securitySchemes" in spec_data["components"]:
            self._scan_security_schemes(spec_data["components"]["securitySchemes"])
        
        # Check parameters
        if "components" in spec_data and "parameters" in spec_data["components"]:
            self._scan_parameters(spec_data["components"]["parameters"])
        
        # Check paths for inline parameters
        if "paths" in spec_data:
            self._scan_paths(spec_data["paths"])
        
        return self.detected_secrets
    
    def _scan_security_schemes(self, schemes: Dict[str, Any]):
        """Scan security schemes for credentials."""
        for scheme_name, scheme_def in schemes.items():
            scheme_type = scheme_def.get("type", "")
            
            if scheme_type == "apiKey":
                self.detected_secrets.append(SecretLocation(
                    path=f"components.securitySchemes.{scheme_name}",
                    field_name=scheme_def.get("name", "apiKey"),
                    secret_type="api_key"
                ))
            
            elif scheme_type == "http":
                if scheme_def.get("scheme") == "bearer":
                    self.detected_secrets.append(SecretLocation(
                        path=f"components.securitySchemes.{scheme_name}",
                        field_name="bearer_token",
                        secret_type="bearer_token"
                    ))
                elif scheme_def.get("scheme") == "basic":
                    self.detected_secrets.append(SecretLocation(
                        path=f"components.securitySchemes.{scheme_name}",
                        field_name="basic_auth",
                        secret_type="basic_auth"
                    ))
            
            elif scheme_type == "oauth2":
                self.detected_secrets.append(SecretLocation(
                    path=f"components.securitySchemes.{scheme_name}",
                    field_name="oauth_client_secret",
                    secret_type="oauth_secret"
                ))
    
    def _scan_parameters(self, parameters: Dict[str, Any]):
        """Scan parameter definitions for secrets."""
        for param_name, param_def in parameters.items():
            if self._is_secret_field(param_name):
                self.detected_secrets.append(SecretLocation(
                    path=f"components.parameters.{param_name}",
                    field_name=param_name,
                    secret_type=self._classify_secret_type(param_name)
                ))
    
    def _scan_paths(self, paths: Dict[str, Any]):
        """Scan path definitions for inline secret parameters."""
        # Filter for valid HTTP methods to avoid crashing on $ref or other keys
        HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}
        for path, path_def in paths.items():
            if not isinstance(path_def, dict):
                continue
            for method, operation in path_def.items():
                if method.lower() not in HTTP_METHODS:
                    continue
                if method.startswith("x-"):  # Skip extensions
                    continue
                
                parameters = operation.get("parameters", [])
                for param in parameters:
                    param_name = param.get("name", "")
                    if self._is_secret_field(param_name):
                        self.detected_secrets.append(SecretLocation(
                            path=f"paths.{path}.{method}.parameters",
                            field_name=param_name,
                            secret_type=self._classify_secret_type(param_name)
                        ))
    
    def _is_secret_field(self, field_name: str) -> bool:
        """Check if a field name indicates it contains a secret."""
        field_lower = field_name.lower()
        return any(
            re.search(pattern, field_lower)
            for pattern in self.SECRET_FIELD_PATTERNS
        )
    
    def _classify_secret_type(self, field_name: str) -> str:
        """Classify the type of secret based on field name."""
        field_lower = field_name.lower()
        
        if "password" in field_lower or "passwd" in field_lower:
            return "password"
        elif "token" in field_lower:
            return "token"
        elif "key" in field_lower:
            return "api_key"
        elif "secret" in field_lower:
            return "secret"
        elif "credential" in field_lower:
            return "credential"
        else:
            return "unknown"


class EnvironmentVariableGenerator:
    """
    Generates environment variable mappings for secrets.
    
    Converts detected secrets into environment variable names
    and generates .env.example files.
    """
    
    def __init__(self):
        self.env_vars: Dict[str, str] = {}
    
    def extract_auth_env_vars(self, auth_info: Dict[str, Any], secrets: List[SecretLocation]) -> Dict[str, str]:
        """
        Extract environment variables needed for authentication.
        
        Args:
            auth_info: Authentication information from spec parser
            secrets: List of detected secrets
            
        Returns:
            Dictionary mapping env var names to descriptions
        """
        env_vars = {}
        
        # Add base URL
        env_vars["API_BASE_URL"] = "Base URL for the API"
        
        # Add secrets as env vars
        for secret in secrets:
            env_var_name = self._secret_to_env_var(secret)
            env_vars[env_var_name] = f"{secret.secret_type.replace('_', ' ').title()} for authentication"
        
        # Add common optional vars
        env_vars["API_TIMEOUT_SECONDS"] = "Request timeout in seconds (default: 30)"
        env_vars["API_MAX_RETRIES"] = "Maximum number of retries for failed requests (default: 3)"
        env_vars["LOG_LEVEL"] = "Logging level (DEBUG, INFO, WARN, ERROR)"
        
        self.env_vars = env_vars
        return env_vars
    
    def _secret_to_env_var(self, secret: SecretLocation) -> str:
        """Convert a secret location to an environment variable name."""
        # Normalize field name to uppercase with underscores
        env_name = secret.field_name.upper()
        env_name = re.sub(r'[^A-Z0-9_]', '_', env_name)
        
        # Ensure it starts with API_ if it doesn't already
        if not env_name.startswith("API_"):
            env_name = f"API_{env_name}"
        
        return env_name
    
    def generate_env_template(self, env_vars: Dict[str, str]) -> str:
        """
        Generate .env.example file content.
        
        Args:
            env_vars: Dictionary of environment variables and descriptions
            
        Returns:
            Content for .env.example file
        """
        lines = [
            "# Environment variables for MCP server",
            "# Copy this file to .env and fill in your actual values",
            "",
            "# Required variables",
            ""
        ]
        
        # Separate required and optional
        required = ["API_BASE_URL", "API_KEY", "API_TOKEN", "API_SECRET"]
        
        for var_name, description in env_vars.items():
            if any(req in var_name for req in required):
                lines.append(f"# {description}")
                lines.append(f"{var_name}=your_{var_name.lower()}_here")
                lines.append("")
        
        lines.append("# Optional configuration")
        lines.append("")
        
        for var_name, description in env_vars.items():
            if not any(req in var_name for req in required):
                lines.append(f"# {description}")
                default = self._get_default_value(var_name)
                lines.append(f"{var_name}={default}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _get_default_value(self, var_name: str) -> str:
        """Get default value for an environment variable."""
        defaults = {
            "API_TIMEOUT_SECONDS": "30",
            "API_MAX_RETRIES": "3",
            "LOG_LEVEL": "INFO",
            "AUDIT_LOG_PATH": "./audit.log"
        }
        return defaults.get(var_name, "")


class InputSanitizer:
    """
    Sanitizes user inputs to prevent injection attacks.
    
    Detects and blocks SQL injection, shell injection, and
    prompt injection attempts.
    """
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(DROP|DELETE|UPDATE)\b.*;)", # Look for semicolon termination
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bOR\b\s+['\"].*['\"]\s*=\s*['\"].*['\"])", # Specific tautology check
    ]
    
    # Shell injection patterns — detect actual command chaining/interpolation,
    # not characters that appear in normal text ($ in currency, & in names).
    SHELL_INJECTION_PATTERNS = [
        r";\s*\w",           # semicolon followed by a command (;ls, ; rm)
        r"\|\s*\w",          # pipe into a command (|cat, | grep)
        r"&&\s*\w",          # logical AND chaining (&& rm)
        r"\|\|\s*\w",        # logical OR chaining (|| rm)
        r"`[^`]+`",          # backtick command substitution (`whoami`)
        r"\$\([^)]+\)",      # $() command substitution ($(whoami))
        r"\$\{[^}]+\}",      # ${} variable expansion (${PATH})
        r"\.\./",            # path traversal (../)
    ]
    
    # Prompt injection patterns
    PROMPT_INJECTION_PATTERNS = [
        r"(ignore\s+(previous|all|above)\s+instructions?)",
        r"(system\s*:)",
        r"(you\s+are\s+now)",
        r"(new\s+instructions?)",
        r"(disregard\s+(previous|all))",
    ]
    
    def sanitize_string_param(self, value: str, param_type: str = "generic") -> str:
        """
        Sanitize a string parameter.
        
        Args:
            value: Input value to sanitize
            param_type: Type of parameter (generic, path, query, header)
            
        Returns:
            Sanitized value
            
        Raises:
            ValueError: If injection attempt detected
        """
        if not isinstance(value, str):
            return value
        
        # Check for injection attempts
        injection_type = self.detect_injection_attempt(value)
        if injection_type:
            raise ValueError(f"Potential {injection_type} injection detected")
        
        # Apply type-specific sanitization
        if param_type == "path":
            return self._sanitize_path_param(value)
        elif param_type == "query":
            return self._sanitize_query_param(value)
        elif param_type == "header":
            return self._sanitize_header_param(value)
        else:
            return self._sanitize_generic_param(value)
    
    def detect_injection_attempt(self, value: str) -> Optional[str]:
        """
        Detect injection attempts in input.
        
        Args:
            value: Input value to check
            
        Returns:
            Type of injection detected, or None if clean
        """
        value_lower = value.lower()
        
        # Check SQL injection
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return "SQL"
        
        # Check shell injection
        for pattern in self.SHELL_INJECTION_PATTERNS:
            if re.search(pattern, value):
                return "shell"
        
        # Check prompt injection
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return "prompt"
        
        return None
    
    def _sanitize_path_param(self, value: str) -> str:
        """Sanitize path parameters."""
        # Remove path traversal attempts
        value = value.replace("../", "").replace("..\\", "")
        # URL encode special characters
        return value
    
    def _sanitize_query_param(self, value: str) -> str:
        """Sanitize query parameters."""
        # HTML escape to prevent XSS
        return html.escape(value, quote=True)
    
    def _sanitize_header_param(self, value: str) -> str:
        """Sanitize header values."""
        # Remove newlines to prevent header injection
        value = value.replace("\r", "").replace("\n", "")
        return value
    
    def _sanitize_generic_param(self, value: str) -> str:
        """Generic sanitization for unknown parameter types."""
        # Remove null bytes
        value = value.replace("\x00", "")
        return value
    
    def escape_special_chars(self, value: str) -> str:
        """
        Escape special characters for safe use.
        
        Args:
            value: Input value
            
        Returns:
            Escaped value
        """
        # Escape backslashes first
        value = value.replace("\\", "\\\\")
        # Escape quotes
        value = value.replace('"', '\\"')
        value = value.replace("'", "\\'")
        return value


# Convenience functions
def detect_secrets(spec_data: Dict[str, Any]) -> List[SecretLocation]:
    """Detect secrets in an OpenAPI spec."""
    detector = SecretDetector()
    return detector.detect_secrets_in_spec(spec_data)


def generate_env_template(auth_info: Dict[str, Any], secrets: List[SecretLocation]) -> str:
    """Generate .env.example file content."""
    generator = EnvironmentVariableGenerator()
    env_vars = generator.extract_auth_env_vars(auth_info, secrets)
    return generator.generate_env_template(env_vars)


def sanitize_input(value: str, param_type: str = "generic") -> str:
    """Sanitize user input."""
    sanitizer = InputSanitizer()
    return sanitizer.sanitize_string_param(value, param_type)


# Made with Bob