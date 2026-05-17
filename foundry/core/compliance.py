"""
Compliance Adapters (Milestone 8).

Provides enterprise-grade compliance scanning for OpenAPI schemas.
Automatically flags PII, PHI, and PCI data and injects `x-compliance-mask` flags 
into the schemas so the Builder agent and Audit logger can enforce redaction.
"""

import re
from typing import Dict, Any, List

class ComplianceScanner:
    """
    Base class for specific industry compliance scanners.
    """
    def __init__(self, name: str, sensitive_patterns: List[str]):
        self.name = name
        self.patterns = [re.compile(p, re.IGNORECASE) for p in sensitive_patterns]

    def is_sensitive(self, field_name: str, description: str = "") -> bool:
        """Check if a field name or description matches compliance patterns."""
        target_text = f"{field_name} {description}"
        for pattern in self.patterns:
            if pattern.search(target_text):
                return True
        return False

    def scan_and_inject(self, schema: Dict[str, Any], path: str = "") -> int:
        """
        Recursively scans an OpenAPI schema object, injecting `x-compliance-mask: true`
        if PII/PCI/PHI fields are detected.
        
        Returns the number of fields flagged.
        """
        flags_added = 0
        
        if not isinstance(schema, dict):
            return flags_added

        # If it's an object with properties, scan its properties
        if "properties" in schema and isinstance(schema["properties"], dict):
            for prop_name, prop_def in schema["properties"].items():
                if isinstance(prop_def, dict):
                    desc = prop_def.get("description", "")
                    
                    if self.is_sensitive(prop_name, desc):
                        prop_def["x-compliance-mask"] = True
                        if "x-compliance-tags" not in prop_def:
                            prop_def["x-compliance-tags"] = []
                        prop_def["x-compliance-tags"].append(self.name)
                        flags_added += 1
                    
                    # Recurse down
                    flags_added += self.scan_and_inject(prop_def, f"{path}.{prop_name}")

        # Handle arrays
        if schema.get("type") == "array" and "items" in schema:
            flags_added += self.scan_and_inject(schema["items"], f"{path}[]")

        # Handle allOf
        if "allOf" in schema and isinstance(schema["allOf"], list):
            for item in schema["allOf"]:
                flags_added += self.scan_and_inject(item, f"{path}.allOf")

        return flags_added


class PCIAdapter(ComplianceScanner):
    """Payment Card Industry (PCI / AML) compliance adapter."""
    def __init__(self):
        super().__init__(
            "PCI-DSS",
            sensitive_patterns=[
                r"credit_?card", r"ssn", r"social_?security", 
                r"routing_?number", r"account_?number", r"card_?number",
                r"cvv", r"cvc", r"billing_?address", r"balance", r"amount"
            ]
        )


class HIPAAAdapter(ComplianceScanner):
    """Healthcare (FHIR / HIPAA) compliance adapter."""
    def __init__(self):
        super().__init__(
            "HIPAA",
            sensitive_patterns=[
                r"patient_?id", r"medical_?record", r"diagnosis",
                r"treatment", r"prescription", r"dob", r"date_?of_?birth",
                r"blood_?type", r"insurance", r"policy_?number", r"health"
            ]
        )


class ComplianceEngine:
    """Runs all registered compliance adapters against the global specification."""
    
    def __init__(self):
        self.adapters = [
            PCIAdapter(),
            HIPAAAdapter()
        ]

    def enforce(self, openapi_spec: Dict[str, Any]) -> Dict[str, int]:
        """
        Scan all schemas in the OpenAPI components block.
        Returns a dictionary mapping adapter name to the number of flagged fields.
        """
        results = {adapter.name: 0 for adapter in self.adapters}
        
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        for schema_name, schema_def in schemas.items():
            for adapter in self.adapters:
                flags = adapter.scan_and_inject(schema_def, schema_name)
                results[adapter.name] += flags
                
        # Also scan parameters in paths
        paths = openapi_spec.get("paths", {})
        for path_name, path_obj in paths.items():
            for method, operation in path_obj.items():
                if not isinstance(operation, dict):
                    continue
                    
                parameters = operation.get("parameters", [])
                for param in parameters:
                    if isinstance(param, dict) and "schema" in param:
                        desc = param.get("description", "")
                        for adapter in self.adapters:
                            if adapter.is_sensitive(param.get("name", ""), desc):
                                param["schema"]["x-compliance-mask"] = True
                                results[adapter.name] += 1
                                
        return results
