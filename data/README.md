# Data & OpenAPI Specification Generator

This directory contains your raw data files (CSV, Excel, JSON) and the `auto_spec_generator.py` utility.

> **Security Note:** Raw datasets (`*.csv`, `*.xlsx`, `*.json`) are explicitly ignored by the repository's `.gitignore` to prevent leaking proprietary data or PII to source control. This folder acts as your secure local sandbox.

## Auto-Spec Generator

The `auto_spec_generator.py` script completely eliminates the manual boilerplate of mapping data columns to API properties. It autonomously loads the first 5 rows of your dataset, infers whether the columns contain strings, numbers, or booleans, and scaffolds a production-ready OpenAPI YAML blueprint directly into the Foundry's `specs/` directory.

### Usage Instructions

1. **Navigate to the data folder:**
   ```bash
   cd data
   ```

2. **Execute the generator against your dataset:**
   ```bash
   # Standard syntax: 
   # python auto_spec_generator.py <filename> --title "<Your Custom API Title>"
   
   # Example for Excel:
   python auto_spec_generator.py whc001.xlsx --title "World Heritage API"
   
   # Example for CSV:
   python auto_spec_generator.py customers.csv --title "Customer API"
   ```

3. **Build your MCP Server:**
   Upon successful execution, the script automatically routes the generated `.yaml` blueprint to the `foundry/specs/` folder. You can immediately build your secure server by running:
   ```bash
   cd ../foundry
   python forge_recipe.py --input specs/<your_generated_file>_api.yaml --output output/<your-server-name> --auto-approve
   ```

4. **Connect Your Data (The Last Mile):**
   The Foundry generates the robust server architecture, but you must link it to your actual spreadsheet. 
   - Open your newly generated `output/<your-server-name>/server/main.py`.
   - Locate the `_call_searchDataset` tool function.
   - Replace the default mocked JSON response with standard Pandas logic:
     ```python
     import pandas as pd
     # Point this to the raw file in your data folder
     df = pd.read_excel(r"C:\absolute\path\to\mcp_server\data\your_file.xlsx")
     
     # Convert the filtered dataframe back to a dictionary for the LLM
     results = df.head(5).to_dict(orient="records")
     ```

5. **Test and Deploy:**
   - Validate your changes: `python -m pytest test_server.py -v`
   - Launch the server: `run_server.bat` (or `run_server.sh`)
   - **The Final Step:** Connect your MCP Client (Claude Desktop, Cursor, or a local Jupyter Notebook running Ollama) directly to the `.bat` file to start chatting securely with your data!

### Supported File Formats
- `.xlsx` / `.xls` (Microsoft Excel)
- `.csv` (Comma-Separated Values)
- `.json` (JavaScript Object Notation)
