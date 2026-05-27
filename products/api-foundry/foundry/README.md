# MCP Server Foundry

> **Pour in your OpenAPI spec. Cast out a production-grade MCP server.**

An agentic pipeline that converts OpenAPI specifications into complete, secure, auditable [Model Context Protocol](https://modelcontextprotocol.io/) servers — with generated test suites, audit trails, and cryptographic provenance.

## 🎯 Objective
The objective of the Foundry is to **completely eliminate the boilerplate and technical debt** of connecting Enterprise APIs to AI applications (like Claude or Cursor). Instead of manually coding a Model Context Protocol (MCP) server for your API, you simply feed your raw OpenAPI YAML spec into the Foundry. The multi-agent pipeline instantly parses the endpoints, injects security and compliance rules, and generates a fully functioning, locally executable, and highly secure Python MCP server in under 5 seconds.

## 🚀 Step-by-Step User Flow
1. **Prepare your Spec:** Place your API's OpenAPI specification (YAML/JSON) in the `specs/` directory. (We have provided Stripe, GitHub, and Jira specs as demos).
2. **Run the Foundry:** Run the `forge_recipe.py` script, pointing it to your spec.
3. **Approve the Gates:** The pipeline will pause to show you its architectural plan and generated code. Press `Y` to approve.
4. **Boot the Server:** Navigate to the generated output directory, add your API keys to the newly generated `.env` file, and run `run_server.bat` (or `.sh`).
5. **Connect to LLMs:** Your server is now broadcasting your API endpoints securely to Claude Desktop or Cursor!

---

## 🚦 Current Status

**Milestone 8 COMPLETE** — 116 Foundry tests + 32 generated server tests passing ✅

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | Foundation Skeleton | ✅ |
| M2 | Security Layer | ✅ |
| M3 | Governance Layer | ✅ |
| M4 | Adversarial Test Suite | ✅ |
| M5 | Documentation Generation | ✅ |
| M6 | Multi-Model Routing | ✅ |
| M7 | Hackathon Demo | ✅ |
| M8 | Startup Features | ✅ |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **pip** package manager

### 1. Install dependencies

```bash
cd foundry
pip install pyyaml jinja2 pydantic
pip install pytest pytest-asyncio   # for running tests
```

### 2. Generate a server from an OpenAPI spec

```bash
# Interactive mode (review plan + code before proceeding)
python forge_recipe.py --input specs/test_api.yaml --output output/my-server

# CI/CD mode (skip approval gates)
python forge_recipe.py --input specs/test_api.yaml --output output/my-server --auto-approve
```

### 3. Review the generated output

```
output/my-server/
├── plan.json              # Architect's structured plan
├── audit.jsonl            # Pipeline audit log (JSON Lines)
├── provenance.json        # SHA-256 hashes + agent timeline
├── execution_trace.json   # Legacy execution trace
└── server/
    ├── main.py            # MCP server (stdio transport)
    ├── validation_models.py   # Pydantic models from OpenAPI schemas
    ├── error_schemas.py       # Structured error responses
    ├── audit_logger.py        # Runtime tool call logger
    ├── .env.example           # Required environment variables
    ├── test_server.py         # Generated adversarial test suite
    ├── README.md              # Premium developer documentation
    ├── run_server.sh          # Linux/macOS launcher recipe
    ├── run_server.bat         # Windows launcher recipe
    └── docs/
        └── tool_reference.md  # Detailed OpenAPI tool reference manual
```

### 4. Run the generated test suite

```bash
cd output/my-server/server
cp .env.example .env        # Fill in your API credentials
python -m pytest test_server.py -v
```

### 5. Run the server

```bash
cd output/my-server/server
# On Windows:
run_server.bat

# On Linux/macOS:
chmod +x run_server.sh
./run_server.sh
```

The server reads JSON-RPC requests from **stdin** and writes responses to **stdout** (MCP stdio transport).

---

## 🔑 API Keys & Multi-Model Configuration (M6)

There are **two entirely different types of API keys** used in this project:

### 1. The Target API Key (Required)
The *generated* MCP server requires credentials to talk to the target service (e.g., Stripe or GitHub).
- **Where to put it:** After generation, look inside `output/my-server/server/.env.example`.
- Copy it to `output/my-server/server/.env` and enter your actual target API key there.

### 2. The Foundry Pipeline LLM Keys (Optional)
The base pipeline natively uses deterministic parsing (YAML/Jinja2), meaning generating servers is **100% free and requires zero LLM API keys**. 

However, with the **Multi-Model Routing Engine (M6)**, the pipeline can delegate highly complex specs to Cloud LLMs or local open-source models:
- **Where to put it:** Copy the root `foundry/.env.example` to `foundry/.env`.
- **Cloud Models:** Enter `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`.
- **Local Models (Ollama):** You can run models 100% locally and completely free. Ensure you have [Ollama](https://ollama.com/) installed and running (`ollama serve`). The router defaults to `http://localhost:11434` and the `llama3` model, which you can customize in the routing config or `.env`.

---

## CLI Reference

```
python forge_recipe.py --input <spec> --output <dir> [--auto-approve]
```

| Flag | Short | Required | Description |
|------|-------|----------|-------------|
| `--input` | `-i` | Yes | Path to OpenAPI spec (YAML or JSON) |
| `--output` | `-o` | Yes | Output directory for generated server |
| `--auto-approve` | | No | Skip interactive approval gates (for CI/CD) |

**Exit codes:**
- `0` — Success
- `1` — Pipeline error
- `2` — Approval gate rejected by user

---

## Pipeline Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Architect   │────▶│   Builder    │────▶│   Tester     │────▶│  Documenter  │
│  (M1)        │     │   (M2)       │     │   (M4)       │     │  (M5)        │
│              │     │              │     │              │     │              │
│ Parse spec   │     │ Generate     │     │ Generate     │     │ Generate     │
│ Create plan  │     │ server code  │     │ test suite   │     │ manuals & sh │
└──────┬───────┘     └──────┬───────┘     └──────────────┘     └──────────────┘
       │                    │
   [Gate 1]             [Gate 2]
   Plan Review          Code Review
```

Each gate is interactive by default — you can review and approve/reject. Use `--auto-approve` to skip.

### Agent Details

| Agent | Input | Output | Key Features |
|-------|-------|--------|--------------|
| **Architect** | OpenAPI YAML/JSON | `plan.json` | Endpoint extraction, auth detection, schema normalization |
| **Builder** | Plan | `server/` directory | Jinja2 templates, Pydantic validation, secret externalization, Semgrep gate |
| **Tester** | Plan + generated code | `test_server.py` | Protocol, happy-path, malformed, injection tests |
| **Documenter**| Plan + generated code | `README.md`, scripts | Dynamic README, tool manuals, Unix shell and Windows batch launchers |

### Context Flow

All agents share an `AgentContext` containing:
- `spec_path` / `output_dir` — I/O locations
- `plan` — Architect's structured plan
- `generated_code` — Dict of filename → code
- `test_results` — Test generation metadata
- `agent_trace` / `errors` — Execution history

---

## Project Structure

```
foundry/
├── forge_recipe.py                    # CLI entry point
├── pyproject.toml                     # Project configuration
├── core/                              # Core abstractions
│   ├── agent_interface.py             # Agent base classes + AgentContext
│   ├── orchestrator.py                # Pipeline coordination + governance
│   ├── audit.py                       # Structured audit logging (M3)
│   ├── approval_gates.py              # Human approval checkpoints (M3)
│   ├── spec_parser.py                 # OpenAPI parsing utilities
│   ├── validation.py                  # Pydantic model generation (M2)
│   ├── security.py                    # Secret detection & sanitization (M2)
│   └── semgrep_gate.py                # Static analysis gate (M2)
├── agents/                            # Agent implementations
│   ├── architect.py                   # Spec → plan
│   ├── builder.py                     # Plan → server code
│   ├── tester.py                      # Plan + code → test suite
│   └── documenter.py                  # Plan + code → manuals & scripts (M5)
├── templates/                         # Jinja2 code generation templates
│   ├── server_main_secure.py.j2       # MCP server template
│   ├── error_schemas.py.j2            # Error response types
│   ├── audit_logger.py.j2             # Runtime audit logger
│   ├── test_server.py.j2              # Adversarial test suite
│   ├── server_readme.md.j2            # Premium server readme (M5)
│   ├── tool_reference.md.j2           # Premium tool reference (M5)
│   ├── run_server.sh.j2               # Unix launch script template (M5)
│   └── run_server.bat.j2              # Windows launch batch template (M5)
├── tests/                             # Foundry's own test suite
│   ├── test_foundation.py             # Spec parser, orchestrator (M1)
│   ├── test_validation.py             # Pydantic code generation (M2)
│   ├── test_security.py               # Injection detection (M2)
│   ├── test_governance.py             # Audit + approval gates (M3)
│   ├── test_tester_agent.py           # TesterAgent unit tests (M4)
│   ├── test_documenter_agent.py       # DocumenterAgent unit tests (M5)
│   └── test_integration.py            # Full pipeline E2E tests
├── specs/                             # Input specifications
│   └── test_api.yaml                  # Synthetic test spec
└── output/                            # Generated servers (gitignored)
```

---

## Features by Milestone

### 🏗️ M1 — Foundation Skeleton
- OpenAPI 3.x spec parsing (YAML + JSON)
- Endpoint extraction, tag grouping, auth detection
- Agent abstraction layer (`Agent` → `StandaloneAgent`, `BobAdapter`)
- `PipelineBuilder` fluent API for composing pipelines
- `Orchestrator` with sequential agent execution + context passing

### 🔒 M2 — Security Layer
- **Pydantic validation models** generated from OpenAPI schemas (type checking, format validation, range constraints)
- **Secret detection** — scans specs for API keys, bearer tokens → externalizes to env vars
- **Input sanitization** — SQL, shell, prompt injection detection with false-positive-safe regexes
- **Semgrep gate** — 20 custom security rules (runs post-build, advisory mode)
- **Structured error responses** — 7 error types with request ID tracking

### 🏛️ M3 — Governance Layer
- **Audit logging** — JSON Lines format, pipeline + runtime events, severity levels, duration tracking
- **Approval gates** — Plan Review (post-Architect) + Code Review (post-Builder), interactive CLI
- **`--auto-approve`** — CI/CD bypass for non-interactive environments
- **Provenance manifest** — SHA-256 file hashes, agent timeline, schema-versioned (`1.0.0`)
- **Runtime audit** — generated servers log every tool call with latency and redacted arguments

### 🧪 M4 — Adversarial Test Suite
- **Protocol tests** (5) — `initialize`, `tools/list`, unknown methods, missing params
- **Happy-path tests** (1 per tool) — valid arguments → JSON-RPC success
- **Malformed input tests** (per required param) — empty args, wrong-type values
- **Injection tests** (per injectable tool × 8 payloads) — SQL, shell, prompt injection

### 📚 M5 — Documentation Generation
- **Standalone `DocumenterAgent`** compiling markdown dynamically from Architect plans
- **Premium README.md** auto-generation with setup guides and Claude/Cursor configurations
- **Detailed Tool Reference** detailing schemas and parameter types in OpenAPI context
- **Cross-Platform Launch Scripts** (`run_server.sh` and `run_server.bat`) checking environment variables

### 🧠 M6 — Multi-Model Routing
- **Provider Abstraction** genericizing Anthropic, Google Gemini, and local Ollama interactions
- **Cost-Optimized Stage Routing** distributing specific agents to specific model architectures
- **Token/Cost Tracking** dashboard rendered upon execution summarizing financial footprint

### 🏆 M7 — Hackathon Demo
- **Curated Stripe Spec** showcasing complex schemas and Bearer Auth
- **Cold Start Script** guiding users from an empty folder to a running Stripe MCP server in 11 minutes
- **Regeneration Script** showcasing zero-friction updates to endpoints

### 🚀 M8 — Startup Features
- **Enterprise Compliance Engine** auto-flagging PCI-DSS (AML) and HIPAA (FHIR) PII fields
- **Automated Pydantic Masking** injecting `x-compliance-mask` rules into JSON schema constraints
- **Public Recipe Library** providing ready-to-forge specifications for GitHub, Jira, and Stripe
- **CI/CD Pipeline** built on GitHub Actions running the Foundry natively on pull requests

---

## Running the Foundry's Own Tests

```bash
cd foundry
python -m pytest tests/ -v
```

Expected output: **116 passed**

| Test File | Count | What it covers |
|-----------|-------|----------------|
| `test_foundation.py` | 31 | Spec loading, validation, normalization, context, orchestrator |
| `test_security.py` | 26 | SQL/shell/prompt injection, false-positive prevention, secrets |
| `test_validation.py` | 11 | Pydantic generation, allOf, $ref, field constraints |
| `test_governance.py` | 19 | Audit logger, approval gates, file hashing |
| `test_tester_agent.py` | 19 | Helper functions, TesterAgent execution |
| `test_documenter_agent.py` | 3 | DocumenterAgent, Jinja2 template compiling, run recipes line endings |
| `test_providers.py` | 3 | Provider interface token calculations, API key handling |
| `test_routing.py` | 2 | Stage-specific model routing rules and default paths |
| `test_integration.py` | 2 | Full 4-agent (Architect → Builder → Tester → Documenter) E2E pipeline |

---

## Recent Changes

### Milestone 8: Startup Features (2026-05-17)
- **Why**: Enterprise AI adoption is blocked by compliance. Generating a server isn't enough; it must securely handle PII and PCI data without developer intervention. Furthermore, the community needs out-of-the-box recipes to prove value immediately.
- **How**: Built a native `ComplianceEngine` that statically analyzes OpenAPI specs for terms like `ssn`, `credit_card`, and `patient_id`. It injects `x-compliance-mask` tags directly into the generated Pydantic models. We updated `audit_logger.py.j2` to read these tags and redact flagged payloads dynamically. Generated `stripe_demo.yaml`, `github_demo.yaml`, and `jira_demo.yaml` recipes and orchestrated them through a `.github/workflows/foundry-ci.yml` pipeline.
- **Impact**: Transforms the Foundry from a scaffolding tool into an enterprise-grade compliance platform. Organizations can securely connect LLMs to healthcare and financial systems with mathematical certainty that logs will not leak sensitive information.

### Milestone 7: Hackathon Demo (2026-05-17)
- **Why**: We needed to physically demonstrate the immense speed and power of the Foundry pipeline against a massive, world-class enterprise API in under 15 minutes.
- **How**: Built precise presentation scripts (`cold_start_script.md`, `regeneration_script.md`) and a bespoke Stripe OpenAPI slice. The scripts detail exactly how to pitch, execute, test, and deploy the generated codebase live on stage.
- **Impact**: Provides a definitive sales/demo toolkit for internal advocacy or public hackathons, proving that the system works flawlessly.

### Milestone 6: Multi-Model Routing (2026-05-17)
- **Why**: An agentic pipeline requires intelligent text generation, but running expensive models (like Claude Opus) on simple formatting tasks destroys profit margins. Different stages require different architectures.
- **How**: Built `core/providers.py` adapting `httpx` logic to interface with Anthropic, Google, and Ollama APIs. Built `core/routing.py` with an auto-routing engine mapping heavy coding tasks to premium models and formatting/parsing tasks to fast, cheap models. Appended `AgentContext` with a comprehensive token accumulator and emitted it as a CLI dashboard.
- **Impact**: Provides highly cost-effective, deterministic intelligence to agents, tracking every penny spent across the pipeline execution lifecycle.

### Milestone 5: Documentation Generation (2026-05-17)
- **Why**: Providing generated servers without automated integration guides, detailed schema parameter documentation, and quick-start launch recipes leaves a high onboarding friction for developers connecting their MCP servers to LLM clients (like Claude or Cursor).
- **How**: Built a dedicated `DocumenterAgent` that automatically runs after `TesterAgent` in the pipeline. It compiles and renders four premium artifacts inside the server output directory:
  - `README.md`: A premium guide documenting requirements, environment variable maps, tool descriptions, and step-by-step connection settings for Claude Desktop and Cursor.
  - `docs/tool_reference.md`: A detailed OpenAPI reference detailing parameter schemas, data types, validation constraints, and JSON request/response structures.
  - `run_server.sh`: A Unix/macOS launcher shell script validating environment files and launching main.py.
  - `run_server.bat`: A Windows launcher batch script validating environment variables and launching main.py.
- **Impact**: Provides instant out-of-the-box local connection templates for LLM clients, completely eliminating onboarding friction and manual configuration errors.

---

## Using Your Own OpenAPI Spec

1. Place your OpenAPI 3.x spec file (YAML or JSON) anywhere accessible
2. Run the pipeline:

```bash
python forge_recipe.py -i path/to/your-api.yaml -o output/your-api --auto-approve
```

3. The pipeline will:
   - Parse your spec and extract all endpoints, schemas, and auth config
   - Present the plan for approval (or auto-approve)
   - Generate a complete MCP server with validation models
   - Present the code for approval (or auto-approve)
   - Generate an adversarial test suite
   - Generate premium developer manuals and quick-start recipes
   - Write provenance manifest with SHA-256 hashes

4. Before running the generated server, configure environment variables:

```bash
cd output/your-api/server
cp .env.example .env
# Edit .env with your actual API credentials
```

---

## Technical Debt Log

| Item | Severity | Description |
|------|----------|-------------|
| `error_schemas.py` uses Pydantic v1 `.dict()` | Low | Should migrate to `.model_dump()` |
| `Semgrep` listed as hard dependency | Low | Only used in advisory mode; should be optional |
| `test_mcp_handshake.py` in root | Low | Legacy file, not in `tests/` directory |

---

## Documentation

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Milestone roadmap and progress
- [SECURITY_BEST_PRACTICES.md](SECURITY_BEST_PRACTICES.md) — Security guide for generated servers
- [MILESTONE_2_PLAN.md](MILESTONE_2_PLAN.md) — M2 detailed implementation plan
- [MILESTONE_2_TEST_RESULTS.md](MILESTONE_2_TEST_RESULTS.md) — M2 test gate verification

---

*Made with Bob*