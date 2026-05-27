# API Foundry (Alpha — Under Active Dev)

An automated OpenAPI 3.0+ to Model Context Protocol (MCP) server generator that builds secure, validated, and structured-logged gateways.

> [!WARNING]
> This product is in **Alpha**. It is currently under active development. See [ROADMAP.md](ROADMAP.md) for planned features and unimplemented items.

## Overview
Writing custom MCP gateway servers for REST APIs is error-prone, resulting in hardcoded secrets, lack of structured logging, and manual schema synchronization. The **API Foundry** automates this by parsing any OpenAPI 3.0 spec, generating Pydantic v2 validation models, and rendering a highly performant FastMCP-based stdio gateway.

## Core Features
1. **FastMCP Generation**: Emits clean servers with one `@mcp.tool()` per OpenAPI operation utilizing standard Stdio transport.
2. **Pydantic Validation**: Converts operation requestBody and parameters schemas to CamelCase Pydantic input models (using `datamodel-code-generator`) for runtime schema compliance.
3. **Environment-Variable Auth**: Dynamically maps Bearer, Basic, and ApiKey security schemes to environment variables (e.g. `API_KEY` / `API_BEARER_TOKEN`) rather than compiling keys into the code.
4. **Structured JSON Logging**: Logs every tool call to stderr as structured JSON with automatic masking of fields matching secret patterns.

## Installation
```bash
cd products/api-foundry
pip install -e .
```

## Quickstart
Run the recipe compiler against your OpenAPI YAML or JSON specification:
```bash
python foundry/forge_recipe.py --input spec.yaml --output ./generated-server --auto-approve
```

Review the compiled output in the `./generated-server/server/` folder!
