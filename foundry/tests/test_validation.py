"""Tests for Pydantic model generation from OpenAPI schemas."""
import pytest
from core.validation import ValidationModelGenerator


class TestBasicModelGeneration:
    """Tests for standard object schema → Pydantic model conversion."""

    def test_simple_object_model(self):
        gen = ValidationModelGenerator()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        code = gen.generate_pydantic_model("User", schema)
        assert "class User(BaseModel):" in code
        assert "name: str" in code

    def test_optional_field(self):
        gen = ValidationModelGenerator()
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
            "required": [],
        }
        code = gen.generate_pydantic_model("Profile", schema)
        assert "Optional[int]" in code

    def test_empty_properties(self):
        gen = ValidationModelGenerator()
        schema = {"type": "object", "properties": {}}
        code = gen.generate_pydantic_model("Empty", schema)
        assert "pass" in code


class TestAllOfComposition:
    """Tests for allOf schema merging — the fix for the dead-code bug."""

    def test_allof_merges_properties(self):
        gen = ValidationModelGenerator()
        schema = {
            "allOf": [
                {"properties": {"a": {"type": "string"}}},
                {"properties": {"b": {"type": "integer"}}},
            ]
        }
        code = gen.generate_pydantic_model("Composite", schema)
        assert "class Composite(BaseModel):" in code
        assert "a:" in code
        assert "b:" in code

    def test_allof_merges_required(self):
        gen = ValidationModelGenerator()
        schema = {
            "allOf": [
                {"properties": {"x": {"type": "string"}}, "required": ["x"]},
                {"properties": {"y": {"type": "integer"}}},
            ]
        }
        code = gen.generate_pydantic_model("Merged", schema)
        # x is required → no Optional wrapper
        assert "x: str" in code
        # y is not required → Optional wrapper
        assert "Optional[int]" in code

    def test_allof_not_blocked_by_processed_schemas(self):
        """Regression test: allOf must run BEFORE processed_schemas guard."""
        gen = ValidationModelGenerator()
        schema = {
            "allOf": [
                {"properties": {"id": {"type": "integer"}}, "required": ["id"]},
            ]
        }
        code = gen.generate_pydantic_model("Item", schema)
        # Must NOT return empty string
        assert code != ""
        assert "class Item(BaseModel):" in code


class TestRefHandling:
    """Tests for $ref schema references."""

    def test_ref_returns_comment(self):
        gen = ValidationModelGenerator()
        schema = {"$ref": "#/components/schemas/Address"}
        code = gen.generate_pydantic_model("Ref", schema)
        assert "Reference to Address" in code

    def test_duplicate_model_returns_empty(self):
        gen = ValidationModelGenerator()
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        gen.generate_pydantic_model("Dup", schema)
        assert gen.generate_pydantic_model("Dup", schema) == ""


class TestFieldConstraints:
    """Tests for Pydantic v2 Field() constraint generation."""

    def test_pattern_uses_pydantic_v2_kwarg(self):
        gen = ValidationModelGenerator()
        schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "pattern": "^[A-Z]{3}$"}
            },
            "required": ["code"],
        }
        code = gen.generate_pydantic_model("Code", schema)
        assert "pattern=" in code
        assert "regex=" not in code

    def test_array_constraints_use_pydantic_v2_kwargs(self):
        gen = ValidationModelGenerator()
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10}
            },
            "required": ["tags"],
        }
        code = gen.generate_pydantic_model("Tagged", schema)
        assert "min_length=1" in code
        assert "max_length=10" in code
        assert "min_items" not in code
        assert "max_items" not in code


class TestImports:
    """Tests for generated import statements."""

    def test_imports_use_field_validator(self):
        gen = ValidationModelGenerator()
        imports = gen.generate_imports()
        assert "field_validator" in imports
        assert "validator" not in imports or "field_validator" in imports
