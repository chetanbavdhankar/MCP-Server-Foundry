import pandas as pd
import yaml
import os
import argparse


############################## README ##########################################
# Simply pass any local file to the script to generate and route the YAML:
# cd c:\Users\cheta\Documents\coding\mcp_server\data
# Example usage for an Excel file
# python auto_spec_generator.py whc001.xlsx --title "World Heritage API"

# Example usage for a CSV
# python auto_spec_generator.py customer_data.csv --title "Customer API"
################################################################################

def infer_openapi_type(dtype):
    """Maps Pandas data types to OpenAPI 3.0 types."""
    dtype_str = str(dtype).lower()
    if 'int' in dtype_str:
        return 'integer'
    elif 'float' in dtype_str:
        return 'number'
    elif 'bool' in dtype_str:
        return 'boolean'
    else:
        return 'string'

def generate_spec(input_file, spec_title="Auto-Generated API"):
    """Reads a data file and outputs an OpenAPI YAML spec to the Foundry folder."""
    
    print(f"Reading {input_file}...")
    ext = os.path.splitext(input_file)[1].lower()
    
    if ext == '.csv':
        df = pd.read_csv(input_file, nrows=5)
    elif ext in ['.xls', '.xlsx']:
        df = pd.read_excel(input_file, nrows=5)
    elif ext == '.json':
        df = pd.read_json(input_file, nrows=5)
    else:
        raise ValueError(f"Unsupported format: {ext}. Use .csv, .xlsx, or .json")
        
    properties = {}
    for col in df.columns:
        properties[col] = {
            "type": infer_openapi_type(df[col].dtype),
            "description": f"Data column: {col}"
        }
        
    openapi_doc = {
        "openapi": "3.0.3",
        "info": {
            "title": spec_title,
            "version": "1.0.0",
            "description": (
                f"Auto-generated API schema from {os.path.basename(input_file)}. "
                f"CRITICAL IMPLEMENTATION INSTRUCTION: Do NOT generate a mock response or HTTP request. "
                f"Inside the tool handler, you MUST `import pandas as pd`, use `pd.read_csv` or `pd.read_excel` "
                f"to load exactly '{os.path.abspath(input_file)}', filter the dataframe using the tool arguments, "
                f"and return the data as a JSON string."
            )
        },
        "paths": {
            "/search": {
                "post": {
                    "summary": f"Search the {spec_title} dataset",
                    "operationId": "searchDataset",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": properties
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "List of matching records",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": properties
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Resolve absolute path to the foundry/specs folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    specs_dir = os.path.abspath(os.path.join(current_dir, '..', 'foundry', 'specs'))
    os.makedirs(specs_dir, exist_ok=True)
    
    # Save the YAML
    base_name = os.path.splitext(os.path.basename(input_file))[0].lower().replace(" ", "_").replace("-", "_")
    output_path = os.path.join(specs_dir, f"{base_name}_api.yaml")
    
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(openapi_doc, f, sort_keys=False)
        
    print(f"[OK] Success! OpenAPI spec deployed to: {output_path}")
    print(f"[->] Run Foundry: python ../foundry/forge_recipe.py --input {output_path} --output ../foundry/output/{base_name}-server --auto-approve")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-generate MCP OpenAPI specs from data files.")
    parser.add_argument("input_file", help="Path to your CSV, Excel, or JSON file")
    parser.add_argument("--title", default="My Dataset", help="Title of your API")
    args = parser.parse_args()
    
    generate_spec(args.input_file, args.title)
