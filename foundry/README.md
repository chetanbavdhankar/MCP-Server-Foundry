# MCP Server Foundry - Implementation

This directory contains the implementation of the MCP Server Foundry pipeline.

## Structure

```
foundry/
├── forge_recipe.py          # Main entry point
├── pyproject.toml           # Python project configuration
├── core/                    # Core abstractions and utilities
│   ├── agent_interface.py   # Agent base classes and context
│   ├── orchestrator.py      # Pipeline coordination
│   └── spec_parser.py       # OpenAPI parsing utilities
├── agents/                  # Agent implementations
│   ├── architect.py         # Spec analysis and planning
│   └── builder.py           # Code generation
├── templates/               # Jinja2 templates for code generation
│   └── server_main.py.j2    # MCP server template
├── specs/                   # OpenAPI specifications
│   └── test_api.yaml        # Synthetic test spec
└── output/                  # Generated servers (gitignored)
```

## Quick Start

### 1. Install dependencies

```bash
cd foundry
pip install pyyaml jinja2 pydantic httpx jsonschema
```

### 2. Run the pipeline

```bash
python forge_recipe.py --input specs/test_api.yaml --output output/test-api
```

### 3. Test the generated server

```bash
cd output/test-api/server
python main.py
```

The server will listen on stdin/stdout for MCP protocol messages.

## Milestone 1 Status

**Foundation Skeleton - COMPLETE**

Implemented:
- ✓ Project scaffolding with proper Python packaging
- ✓ Synthetic test OpenAPI specification
- ✓ Agent abstraction layer with Bob adapter stub
- ✓ Architect agent (spec parsing and planning)
- ✓ Builder agent (code generation)
- ✓ Recipe engine with CLI interface
- ✓ Orchestrator for agent coordination

Ready for test gates.

## Architecture

### Agent Abstraction Layer

The system uses an abstract `Agent` base class that allows for both standalone execution and future IBM Bob integration:

- `StandaloneAgent`: Local execution (current implementation)
- `BobAdapter`: Future IBM Bob mode integration (stub)

### Execution Flow

1. **Architect Agent**: Parses OpenAPI spec, creates structured plan
2. **Builder Agent**: Generates MCP server code from plan
3. **Orchestrator**: Coordinates agent execution, manages context passing

### Context Passing

All agents share an `AgentContext` object that contains:
- Input spec data
- Generated artifacts (plan, code, tests, docs)
- Execution trace
- Error log

## Next Steps

- Run Milestone 1 test gates
- Implement Milestone 2 (Security layer)
- Add Tester agent (Milestone 4)
- Add Documenter agent (Milestone 5)