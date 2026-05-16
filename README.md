# MCP Server Foundry

> **Pour in your OpenAPI spec. Cast out a production-grade MCP server.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Built with IBM Bob](https://img.shields.io/badge/Built%20with-IBM%20Bob-0f62fe.svg)](https://www.ibm.com/bob)
[![MCP Protocol](https://img.shields.io/badge/Protocol-MCP-6366f1.svg)](https://modelcontextprotocol.io)
[![Status: Hackathon Alpha](https://img.shields.io/badge/Status-Hackathon%20Alpha-amber.svg)]()

---

## What is MCP Server Foundry?

**MCP Server Foundry** is an IBM Bob-powered agentic pipeline that converts any OpenAPI specification into a complete, deployable, auditable Model Context Protocol (MCP) server — automatically, repeatably, and with production-grade defaults baked in from the first run.

Every team building agentic AI systems in 2026 ends up hand-rolling the same MCP server, and making the same mistakes: hallucinated parameters accepted without schema validation, secrets embedded in tool definitions, no audit logging, no adversarial tests. The Foundry solves this at the source.

**The first MCP server takes 11 minutes. Every one after that takes 4. Replayable forever.**

### LLM-agnostic by design

The Foundry is provider-neutral at both layers:

- **Generation time** — you choose which LLM builds your server. Default routing uses IBM Granite and Anthropic Claude through Bob, but the provider layer is abstracted. Configure any combination of Anthropic, OpenAI, Google Gemini, xAI Grok, Mistral, or local models via Ollama per pipeline stage.
- **Runtime** — the generated MCP server is just a server. Any MCP-compatible client connects to it: Claude Desktop, Gemini, GPT, Grok, or a local Ollama-backed agent. The protocol is open by design.

No vendor lock-in at either end.

---

## The problem in one paragraph

Writing one MCP server is annoying. Writing the tenth is a waste of senior engineering time. Each hand-rolled server accumulates the same class of boring-but-critical failures: loose input validation, hardcoded credentials, raw error messages leaking internals to calling agents, no structured rate-limit handling, and no way to regenerate cleanly when the upstream API changes. The Foundry eliminates this entire class of failure by making correct-by-construction defaults the path of least resistance.

---

## Key numbers

| Metric | Value |
|---|---|
| Time to first server (cold start) | ~11 minutes |
| Time to regenerate after API change | ~4 minutes |
| IBM Bob primitives used in pipeline | 9 |
| Hand-rolled boilerplate required | 0 |
| Human approval gates per run | 2 |
| Re-runs when upstream spec changes | Unlimited |

---

## How it works

The Foundry is a four-agent Bob pipeline orchestrated by a single BobShell recipe. One command triggers the full sequence. The recipe is the primary artifact — the generated server is the byproduct.

```
openapi_spec.yaml
       │
       ▼
┌─────────────────┐
│  Bob Architect  │  Parse spec → build dependency graph → output plan.json
│     (mode)      │  Model: IBM Granite (cost-optimized for parsing)
└────────┬────────┘
         │
         ▼
  ┌─────────────┐
  │  GATE 1     │  Human approval: review plan, modify scope, approve
  └─────────────┘
         │
         ▼
┌─────────────────┐
│  Bob Builder    │  Generate full MCP server with security defaults
│     (mode)      │  Model: Claude Sonnet (reasoning-intensive codegen)
│                 │  → Strict input validation from spec schemas
│                 │  → Env-var-based secret handling (no hardcoded creds)
│                 │  → Structured error responses for all failure modes
│                 │  → Audit logging in every tool handler
│                 │  → Inline Semgrep scan (build gate — fails on violations)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Bob Tester     │  Generate and run adversarial test suite
│     (mode)      │  Model: Claude (extended reasoning for edge cases)
│                 │  → Happy-path unit tests for every tool
│                 │  → Malformed input tests (wrong types, missing fields)
│                 │  → Injection attempt tests (prompt, SQL, shell)
│                 │  → Rate limit and auth failure simulation
└────────┬────────┘
         │
         ▼
  ┌─────────────┐
  │  GATE 2     │  Human approval: review test results, approve deployment
  └─────────────┘
         │
         ▼
┌─────────────────┐
│  Bob Documenter │  Generate complete output package
│     (mode)      │  Model: IBM Granite (cost-optimized for docs)
│                 │  → README with getting-started guide
│                 │  → Environment variable reference
│                 │  → Tool reference documentation
│                 │  → BobShell recipe file (the replayable artifact)
│                 │  → Cryptographic provenance manifest
└────────┬────────┘
         │
         ▼
  output/
  ├── server/          # The generated MCP server (Python)
  ├── tests/           # Full adversarial test suite
  ├── docs/            # README, env ref, tool ref
  ├── forge.recipe     # BobShell recipe — re-run this when the API changes
  └── manifest.json    # Cryptographic provenance record
```

---

## IBM Bob features used

| Bob feature | Role in the Foundry | Why it matters |
|---|---|---|
| **Architect mode** | Spec parsing and dependency planning | Understands system structure before writing code |
| **Builder / Code mode** | Full MCP server code generation | Production-grade output, not skeleton boilerplate |
| **Orchestrator mode** | Chains four agents with handoffs and approval gates | The pipeline is the product, not a one-shot script |
| **BobShell literate workflows** | User-facing entry point — one command, fully reproducible | Re-runnable when the upstream API changes |
| **Multi-model routing** | Lighter models for parsing, stronger for generation | Cost-optimized automatically per task type |
| **Inline Semgrep scanning** | Build gate — generated code must pass static analysis | Catches security issues before deployment |
| **Secrets detection** | Refuses to embed auth values into tool schemas | Prevents the most common MCP security mistake |
| **Findings panel** | Surfaces MCP-spec compliance issues during generation | Developer sees issues inline, not post-deployment |
| **Approval checkpoints** | Human review gates between plan, code, and ship | Governance baked in, not bolted on |

---

## What the Foundry generates

Every output package contains a complete, deployable MCP server with the following built in by default — no configuration required.

### Security defaults

- **Strict input validation** — Pydantic models generated directly from OpenAPI parameter schemas. Every tool rejects inputs that do not match the spec. No hallucinated parameters accepted by the server.
- **Env-var-based secret handling** — All API keys, tokens, and credentials detected in the spec are lifted to environment variable references. Nothing sensitive appears in source code.
- **Structured error responses** — Every failure mode (validation error, auth failure, rate limit, network timeout) returns a structured error schema that calling agents can reason about. No raw stack traces exposed.
- **Injection-resistant handlers** — All string parameters are sanitized before reaching the HTTP layer. Prompt injection, SQL injection, and shell metacharacter tests are included in the generated test suite.

### Observability defaults

- **Audit logging** — Every tool invocation logs: timestamp, tool name, sanitized input parameters, response status, and latency. Log format is structured JSON, ready for ingestion into any SIEM or observability platform.
- **Provenance manifest** — Every generated package includes a signed `manifest.json` with the SHA-256 of the input spec, Forge version, Bob version, model routing configuration, and generation timestamp. Fully verifiable by a third party.

### Regenerability

- **BobShell recipe** — The recipe file encodes the full generation pipeline. When the upstream API releases a new version, re-running the recipe produces an updated server with a clean diff against the previous output. No manual edits required.
- **Execution trace** — A complete log of every Bob agent action, decision, and model call that produced the output. Enterprises can reproduce the generation exactly from this trace for compliance purposes.

---

## Quickstart

### Prerequisites

- IBM Bob (Pro tier or above — requires BobShell and Orchestrator mode)
- Python 3.11+
- An OpenAPI specification file (YAML or JSON, v3.0+)

### Installation

```bash
# Clone the Foundry
git clone https://github.com/your-org/mcp-server-foundry
cd mcp-server-foundry

# Install Python dependencies
pip install -r requirements.txt

# Verify Bob is available
bob --version
```

### Run the Foundry

```bash
# Basic run — provide your OpenAPI spec
bob shell forge.recipe --input ./your-api-spec.yaml --output ./output/

# With a named output
bob shell forge.recipe \
  --input ./specs/stripe.yaml \
  --output ./output/stripe-mcp/ \
  --name "Stripe MCP Server"
```

The pipeline will:
1. Parse your spec and show you a plan (Gate 1 — your approval required)
2. Generate the server, run Semgrep, and apply security defaults
3. Run the full adversarial test suite and show results (Gate 2 — your approval required)
4. Generate documentation and the BobShell recipe

### Regenerate after an API update

```bash
# When the upstream API releases a new spec version
bob shell output/stripe-mcp/forge.recipe --input ./specs/stripe-v2.yaml

# Review the diff
diff output/stripe-mcp/server/ output/stripe-mcp-v2/server/
```

---

## Output structure

```
output/
├── server/
│   ├── main.py              # MCP server entry point
│   ├── tools/               # One file per API endpoint group
│   │   ├── payments.py
│   │   ├── customers.py
│   │   └── ...
│   ├── validation/          # Pydantic models from spec schemas
│   ├── errors/              # Structured error response schemas
│   ├── logging/             # Audit logging configuration
│   └── requirements.txt     # Python dependencies
├── tests/
│   ├── test_happy_path.py   # Valid input tests for every tool
│   ├── test_malformed.py    # Edge case and invalid input tests
│   ├── test_injection.py    # Injection attempt tests
│   └── test_rate_limits.py  # Rate limit and auth failure tests
├── docs/
│   ├── README.md            # Getting-started guide
│   ├── ENV_VARS.md          # Environment variable reference
│   └── TOOLS.md             # Tool reference documentation
├── forge.recipe             # BobShell recipe — the replayable artifact
└── manifest.json            # Cryptographic provenance record
```

---

## LLM provider configuration

The Foundry abstracts LLM selection behind a `providers.yaml` config. You can route any pipeline stage to any supported provider — mix and match across stages to optimize for cost, accuracy, or latency.

### Default routing (cost-optimized)

```yaml
generation:
  architect:
    provider: ibm
    model: granite-3.0-8b
    purpose: "Spec parsing and planning — lightweight, cost-optimized"

  builder:
    provider: anthropic
    model: claude-sonnet-4
    purpose: "Code generation — reasoning-heavy, accuracy-critical"

  tester:
    provider: anthropic
    model: claude-sonnet-4
    purpose: "Adversarial test generation — extended reasoning"

  documenter:
    provider: ibm
    model: granite-3.0-8b
    purpose: "Documentation — cost-optimized"
```

### Multi-vendor example

```yaml
generation:
  architect:   { provider: google,    model: gemini-3.1-pro }
  builder:     { provider: openai,    model: gpt-5.5 }
  tester:      { provider: xai,       model: grok-4.3 }
  documenter:  { provider: mistral,   model: mistral-large-2 }
```

### Fully local example (zero cloud calls)

```yaml
generation:
  architect:   { provider: ollama, model: qwen2.5-coder:7b }
  builder:     { provider: ollama, model: qwen2.5-coder:32b }
  tester:      { provider: ollama, model: qwen2.5-coder:14b }
  documenter:  { provider: ollama, model: llama3.2:8b }
```

### Supported providers

| Provider | Models | Notes |
|---|---|---|
| `anthropic` | Claude Sonnet, Claude Opus, Claude Haiku | Best for code generation and reasoning |
| `openai` | GPT-5.5, GPT-4o, o3-mini | Strong general-purpose alternative |
| `google` | Gemini 3.1 Pro, Gemini Flash | Long-context strength for large specs |
| `xai` | Grok 4.3, Grok 4 | Alternative reasoning model |
| `ibm` | Granite 3.0 family | Cost-optimized via Bob native integration |
| `mistral` | Mistral Large, Codestral | EU-hosted option for data residency |
| `ollama` | Qwen, Llama, DeepSeek, any GGUF | Fully local, zero network egress |
| `azure-openai` | Same as OpenAI | For Azure-resident enterprise customers |
| `bedrock` | Claude, Llama, Mistral via AWS | For AWS-resident enterprise customers |

API keys for each provider are read from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, etc.) — never embedded in `providers.yaml`.

### Runtime LLM compatibility

The generated MCP server itself contains no LLM. Any MCP-compatible client can connect:

- Claude Desktop, Claude API
- Gemini via MCP adapter
- GPT via MCP adapter
- Grok via MCP adapter
- Local Ollama-backed agents
- Custom LangGraph, LangChain, or hand-rolled agents

If a new LLM ships tomorrow with MCP support, it works with every server the Foundry has ever generated. No regeneration required.

---

## Environment variables

Every generated server reads configuration from environment variables. The full list is in `docs/ENV_VARS.md` in the output package. A typical generated `.env.example` looks like:

```env
# API Authentication
API_KEY=                    # Required. Your API key for the upstream service.
API_BASE_URL=               # Required. Base URL of the upstream API.

# Optional configuration
API_TIMEOUT_SECONDS=30      # Default: 30. Request timeout in seconds.
API_MAX_RETRIES=3           # Default: 3. Retries on transient failures.
AUDIT_LOG_PATH=./audit.log  # Default: stdout. Path for audit log output.
LOG_LEVEL=INFO              # Default: INFO. One of DEBUG, INFO, WARN, ERROR.
```

No secrets ever appear in source files. The Foundry will fail the Semgrep build gate if any credential is detected in generated code.

---

## Running the generated server

```bash
cd output/your-api-mcp/server/

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your actual credentials

# Start the MCP server
python main.py

# The server listens on stdio by default (MCP standard transport)
# For HTTP transport:
python main.py --transport http --port 8080
```

---

## Running the test suite

```bash
cd output/your-api-mcp/

# Run the full adversarial test suite
pytest tests/ -v

# Run only happy-path tests
pytest tests/test_happy_path.py -v

# Run only security tests
pytest tests/test_injection.py tests/test_malformed.py -v
```

---

## Connecting to an agent

Once the server is running, connect it to your agentic solution by adding it to your MCP client configuration. Example for Claude Desktop or any MCP-compatible client:

```json
{
  "mcpServers": {
    "your-api": {
      "command": "python",
      "args": ["./output/your-api-mcp/server/main.py"],
      "env": {
        "API_KEY": "${YOUR_API_KEY}",
        "API_BASE_URL": "https://api.yourservice.com/v1"
      }
    }
  }
}
```

For LangGraph or custom agent frameworks:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["./output/your-api-mcp/server/main.py"],
    env={"API_KEY": "your-key", "API_BASE_URL": "https://api.yourservice.com/v1"}
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        # Your agent now has access to all generated tools
```

---

## Implementation milestones

The Foundry is built in eight milestones with a test gate between each. No milestone starts until the previous one passes.

| Milestone | Layer | Deliverable | Test gate |
|---|---|---|---|
| M1 | Foundation | Skeleton pipeline — OpenAPI in, stub server out | Pipeline runs end to end; server starts and responds |
| M2 | Security | Strict validation, secret handling, Semgrep gate | Malformed inputs rejected; no secrets in source files |
| M3 | Governance | Audit logging, approval checkpoints, execution trace | Audit log present; pipeline halts at approval gates |
| M4 | Testing | Adversarial test suite generation and execution | All test categories pass; suite included in output |
| M5 | Documentation | Complete output package and BobShell recipe | Developer can onboard in under 5 minutes from README |
| M6 | Optimization | Multi-model routing for cost efficiency | 30%+ cost reduction vs single-model baseline |
| M7 | Demo | Hackathon demo script — 11 min live run | Full pipeline on Stripe spec under 11 min cold |
| M8 | Startup | Compliance adapter, recipe library, provenance | Financial adapter passes mock regulatory audit |

---

## Defensive moat

The Foundry is defensible in seven ways that a weekend competitor cannot replicate:

1. **Data flywheel** — every schema failure and auth edge case across all runs improves the default templates. This data accumulates over time and is not copyable.
2. **Recipe library network effect** — a growing public library of pre-validated recipes for popular APIs (Stripe, Salesforce, GitHub, Jira) creates first-mover stickiness.
3. **Regulated-industry compliance adapters** — domain-specific adapters for AML, FHIR, and GDPR encode regulatory requirements that generic competitors lack the domain expertise to build.
4. **Cryptographic provenance** — every server has a verifiable audit trail. For regulated industries this is a legal requirement, not a feature.
5. **MCP Forge Certified badge** — a trust signal that the server was generated, tested, and audited by the Foundry. Standards-body stickiness.
6. **Regenerability as CI/CD primitive** — once the Foundry is in a team's pipeline, triggered automatically on spec changes, switching costs become very high.
7. **LLM-agnostic by design** — works with any provider at generation time and any MCP-compatible client at runtime. Competitors locked into a single vendor cannot match this flexibility, especially for enterprise customers with data residency or vendor diversification requirements.

---

## Business model

| Tier | Price | What is included |
|---|---|---|
| **Open core** | Free | Core Foundry engine, community recipe library, local runs |
| **Pro / Teams** | $49–$199/month | Hosted regeneration pipeline, CI/CD integration, private recipe library, adversarial test suite, multi-model cost routing dashboard |
| **Enterprise compliance** | Custom | AML/FHIR/GDPR domain adapters, cryptographic provenance tracking, full audit trail export, on-prem deployment, SLAs |

---

## Roadmap

- [ ] M1 — Skeleton pipeline (Week 1)
- [ ] M2 — Security layer (Week 1–2)
- [ ] M3 — Governance layer (Week 2)
- [ ] M4 — Adversarial test suite (Week 2–3)
- [ ] M5 — Documentation and packaging (Week 3)
- [ ] M6 — Multi-model routing (Week 3–4)
- [ ] M7 — Hackathon demo (Week 4)
- [ ] M8 — Compliance adapter and recipe library (Month 2+)
- [ ] GitHub Actions integration for automatic regeneration on spec change
- [ ] Public recipe library launch (Stripe, Salesforce, GitHub, Jira, HubSpot)
- [ ] Financial services compliance adapter (AML, transaction monitoring)
- [ ] Healthcare compliance adapter (FHIR, HL7)
- [ ] Public transparency log for provenance manifests

---

## Contributing

The core Foundry engine is open source. Contributions are welcome, especially:

- New recipe library entries for popular APIs
- Domain-specific compliance adapters
- Additional Semgrep rules for MCP-specific security patterns
- Test case improvements for the adversarial suite

Please open an issue before starting large contributions so we can discuss approach and avoid duplication.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

The compliance adapters (financial services, healthcare) are proprietary and available under the Enterprise tier.

---

## Acknowledgements

Built with [IBM Bob](https://www.ibm.com/bob) — the agentic development platform that makes the Foundry's four-agent pipeline possible.

Built on the [Model Context Protocol](https://modelcontextprotocol.io) open standard from Anthropic.

---

*The forge is the artifact. The servers are byproducts.*