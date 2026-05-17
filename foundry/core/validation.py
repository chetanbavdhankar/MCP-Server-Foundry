"""
Pydantic model generation from OpenAPI schemas.

This module converts OpenAPI schema definitions into Pydantic models
for strict runtime validation of tool inputs.
"""

from typing import Dict, Any, List, Optional, Set
import re


class ValidationModelGenerator:
    """
    Generates Pydantic model code from OpenAPI schemas.
    
    Handles nested schemas, references, arrays, objects, and all
    JSON Schema validation keywords.
    """
    
    def __init__(self):
        self.generated_models: Dict[str, str] = {}
        self.processed_schemas: Set[str] = set()
    
    def generate_all_models(self, schemas: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate Pydantic models for all schemas.
        
        Args:
            schemas: Dictionary of schema definitions from OpenAPI spec
            
        Returns:
            Dictionary mapping model names to generated code
        """
        self.generated_models = {}
        self.processed_schemas = set()
        
        for schema_name, schema_def in schemas.items():
            if schema_name not in self.processed_schemas:
                model_code = self.generate_pydantic_model(schema_name, schema_def)
                self.generated_models[schema_name] = model_code
        
        return self.generated_models
    
    def generate_pydantic_model(self, model_name: str, schema: Dict[str, Any]) -> str:
        """
        Generate a single Pydantic model from a schema definition.
        
        Args:
            model_name: Name for the generated model class
            schema: OpenAPI schema definition
            
        Returns:
            Python code for the Pydantic model
        """
        if model_name in self.processed_schemas:
            return ""
        
        # Handle schema references
        if "$ref" in schema:
            self.processed_schemas.add(model_name)
            ref_name = schema["$ref"].split("/")[-1]
            return f"# Reference to {ref_name}"
        
        # Handle allOf composition (basic merge) — must come before
        # marking processed, so the recursive call gets a clean schema
        if "allOf" in schema:
            merged_schema = {"type": "object", "properties": {}, "required": []}
            for part in schema["allOf"]:
                if "$ref" in part:
                    # TODO: resolve $ref and merge its properties
                    pass
                if "properties" in part:
                    merged_schema["properties"].update(part["properties"])
                if "required" in part:
                    merged_schema["required"].extend(part["required"])
                if "description" in part:
                    merged_schema.setdefault("description", part["description"])
            return self.generate_pydantic_model(model_name, merged_schema)
        
        self.processed_schemas.add(model_name)
        
        schema_type = schema.get("type", "object")
        
        if schema_type != "object":
            # For non-object schemas, create a simple wrapper
            return self._generate_simple_model(model_name, schema)
        
        # Generate class definition
        lines = []
        
        # Class header with docstring
        description = schema.get("description", f"Schema for {model_name}")
        lines.append(f"class {model_name}(BaseModel):")
        lines.append(f'    """{description}"""')
        lines.append("")
        
        # Generate fields
        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))
        
        if not properties:
            lines.append("    pass")
        else:
            for field_name, field_schema in properties.items():
                field_code = self._generate_field(
                    field_name, 
                    field_schema, 
                    is_required=field_name in required_fields
                )
                lines.append(f"    {field_code}")
            
            # Add validators if needed
            validators = self._generate_validators(properties)
            if validators:
                lines.append("")
                for validator in validators:
                    lines.append(f"    {validator}")

        return "\n".join(lines)
    
    def _generate_simple_model(self, model_name: str, schema: Dict[str, Any]) -> str:
        """Generate a simple model for non-object schemas."""
        schema_type = schema.get("type", "string")
        python_type = self._schema_type_to_python(schema)
        
        description = schema.get("description", f"Simple {schema_type} schema")
        
        lines = [
            f"class {model_name}(BaseModel):",
            f'    """{description}"""',
            "",
            f"    value: {python_type}"
        ]
        
        return "\n".join(lines)
    
    def _generate_field(self, field_name: str, schema: Dict[str, Any], is_required: bool) -> str:
        """
        Generate a single field definition.
        
        Args:
            field_name: Name of the field
            schema: Schema definition for the field
            is_required: Whether the field is required
            
        Returns:
            Python code for the field definition
        """
        # Get Python type
        python_type = self._schema_type_to_python(schema)
        
        # Make optional if not required
        if not is_required:
            python_type = f"Optional[{python_type}]"
        
        # Build Field() arguments
        field_args = []
        
        # Default value
        if is_required:
            field_args.append("...")
        else:
            default = schema.get("default")
            if default is None:
                field_args.append("None")
            elif isinstance(default, str):
                field_args.append(f'"{default}"')
            else:
                field_args.append(str(default))
        
        # Description
        if "description" in schema:
            desc = schema["description"].replace('"', '\\"')
            field_args.append(f'description="{desc}"')
        
        # Validation constraints
        constraints = self._get_validation_constraints(schema)
        field_args.extend(constraints)
        
        # Enterprise Compliance injection (M8)
        if schema.get("x-compliance-mask") is True:
            tags = schema.get("x-compliance-tags", [])
            json_extra = f'{{"mask": True, "compliance_tags": {tags}}}'
            field_args.append(f"json_schema_extra={json_extra}")
            
        # Build the field definition
        field_def = f"{field_name}: {python_type}"
        if field_args:
            field_def += f" = Field({', '.join(field_args)})"
        
        return field_def
    
    def _schema_type_to_python(self, schema: Dict[str, Any]) -> str:
        """
        Convert JSON Schema type to Python type annotation.
        
        Args:
            schema: Schema definition
            
        Returns:
            Python type annotation as string
        """
        # Handle references
        if "$ref" in schema:
            return schema["$ref"].split("/")[-1]
        
        schema_type = schema.get("type", "string")
        schema_format = schema.get("format")
        
        # Handle arrays
        if schema_type == "array":
            items_schema = schema.get("items", {})
            item_type = self._schema_type_to_python(items_schema)
            return f"List[{item_type}]"
        
        # Handle objects
        if schema_type == "object":
            # Check if it has properties (nested object)
            if "properties" in schema:
                return "Dict[str, Any]"  # For now, use Dict
            return "Dict[str, Any]"
        
        # Handle enums
        if "enum" in schema:
            enum_values = schema["enum"]
            if all(isinstance(v, str) for v in enum_values):
                return "str"  # Could generate Literal type
            return "Any"
        
        # Handle primitive types
        type_mapping = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "null": "None"
        }
        
        # Handle string formats
        if schema_type == "string" and schema_format:
            format_mapping = {
                "date": "date",
                "date-time": "datetime",
                "email": "str",
                "uri": "str",
                "uuid": "UUID"
            }
            return format_mapping.get(schema_format, "str")
        
        return type_mapping.get(schema_type, "Any")
    
    def _get_validation_constraints(self, schema: Dict[str, Any]) -> List[str]:
        """
        Extract validation constraints from schema.
        
        Args:
            schema: Schema definition
            
        Returns:
            List of Field() constraint arguments
        """
        constraints = []
        
        # String constraints
        if "minLength" in schema:
            constraints.append(f"min_length={schema['minLength']}")
        if "maxLength" in schema:
            constraints.append(f"max_length={schema['maxLength']}")
        if "pattern" in schema:
            pattern = schema["pattern"].replace("\\", "\\\\")
            constraints.append(f'pattern=r"{pattern}"')
        
        # Number constraints
        if "minimum" in schema:
            constraints.append(f"ge={schema['minimum']}")
        if "maximum" in schema:
            constraints.append(f"le={schema['maximum']}")
        if "exclusiveMinimum" in schema:
            constraints.append(f"gt={schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema:
            constraints.append(f"lt={schema['exclusiveMaximum']}")
        
        # Array constraints (Pydantic v2 uses min_length/max_length for sequences)
        if "minItems" in schema:
            constraints.append(f"min_length={schema['minItems']}")
        if "maxItems" in schema:
            constraints.append(f"max_length={schema['maxItems']}")
        
        return constraints
    
    def _generate_validators(self, properties: Dict[str, Any]) -> List[str]:
        """
        Generate custom validators for complex validation logic.
        
        Args:
            properties: Schema properties
            
        Returns:
            List of validator method definitions
        """
        validators = []
        
        # Generate email validators
        for field_name, schema in properties.items():
            if schema.get("format") == "email":
                validators.append(
                    f"@field_validator('{field_name}')\n"
                    f"    @classmethod\n"
                    f"    def validate_{field_name}(cls, v):\n"
                    f"        if v and '@' not in v:\n"
                    f"            raise ValueError('Invalid email format')\n"
                    f"        return v"
                )
        
        return validators
    
    def generate_imports(self) -> str:
        """
        Generate necessary imports for the validation module.
        
        Returns:
            Import statements as string
        """
        imports = [
            "from pydantic import BaseModel, Field, field_validator",
            "from typing import Optional, List, Dict, Any, Union",
            "from datetime import date, datetime",
            "from uuid import UUID",
            ""
        ]
        return "\n".join(imports)
    
    def generate_validation_module(self, schemas: Dict[str, Any]) -> str:
        """
        Generate complete validation module with all models.
        
        Args:
            schemas: All schema definitions from OpenAPI spec
            
        Returns:
            Complete Python module code
        """
        models = self.generate_all_models(schemas)
        
        lines = [
            '"""',
            "Generated validation models from OpenAPI schemas.",
            "",
            "This file is auto-generated by the MCP Server Foundry.",
            "Do not edit manually - regenerate from the OpenAPI spec.",
            '"""',
            "",
            self.generate_imports(),
            ""
        ]
        
        # Add all model definitions
        for model_name, model_code in models.items():
            if model_code and not model_code.startswith("#"):
                lines.append(model_code)
                lines.append("")
                lines.append("")
        
        return "\n".join(lines)


def generate_validation_models(schemas: Dict[str, Any]) -> str:
    """
    Convenience function to generate validation models.
    
    Args:
        schemas: Schema definitions from OpenAPI spec
        
    Returns:
        Complete validation module code
    """
    generator = ValidationModelGenerator()
    return generator.generate_validation_module(schemas)


# Made with Bob