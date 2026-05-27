"""
Pydantic model generation from OpenAPI schemas using datamodel-code-generator.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

def generate_validation_models(schemas: Dict[str, Any]) -> str:
    """
    Generate Pydantic v2 models from OpenAPI schemas using datamodel-code-generator.
    
    Args:
        schemas: Schema definitions from the OpenAPI specification
        
    Returns:
        Complete Python module code with Pydantic models
    """
    if not schemas:
        return "# No schemas found\nfrom pydantic import BaseModel, Field\n"

    # Wrap schemas in a minimal OpenAPI spec so datamodel-code-generator can parse it
    minimal_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Stub API",
            "version": "1.0.0"
        },
        "paths": {},
        "components": {
            "schemas": schemas
        }
    }
    
    # Write spec to temporary JSON file
    temp_spec_fd, temp_spec_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(temp_spec_fd, 'w', encoding='utf-8') as f:
            json.dump(minimal_spec, f)
            
        # Allocate a temp file for output code
        temp_out_fd, temp_out_path = tempfile.mkstemp(suffix=".py")
        os.close(temp_out_fd)
        
        try:
            from datamodel_code_generator import generate, InputFileType, PythonVersion
            
            # Pass Path objects to ensure datamodel-code-generator correctly parses it as a filepath
            generate(
                input_=Path(temp_spec_path),
                input_file_type=InputFileType.OpenAPI,
                output=Path(temp_out_path),
                target_python_version=PythonVersion.PY_310,
                use_schema_description=True,
                use_double_quotes=True,
                use_standard_collections=True,
                validation=True,
            )
            
            with open(temp_out_path, 'r', encoding='utf-8') as f:
                code = f.read()
                
            return code
        except Exception as e:
            print(f"[Warning] datamodel-code-generator failed: {e}")
            return "# Pydantic models generation failed\nfrom pydantic import BaseModel, Field\n"
        finally:
            try:
                os.unlink(temp_out_path)
            except Exception:
                pass
    finally:
        try:
            os.unlink(temp_spec_path)
        except Exception:
            pass