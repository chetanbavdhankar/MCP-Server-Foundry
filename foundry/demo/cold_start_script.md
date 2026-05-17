# Foundry Hackathon Demo: 11-Minute Cold Start

**Objective:** Prove that the Foundry can instantly ingest a massive, raw OpenAPI specification (like Stripe's) and safely scaffold a fully functioning, highly auditable MCP server in seconds.

## ⏱️ Prep (T-minus 2 minutes)
1. Have a clean terminal open in the root `foundry/` directory.
2. Have Claude Desktop or Cursor open in the background.
3. Keep `specs/stripe_demo.yaml` visible to show the raw schema.

## 🎬 The Demo (11 Minutes)

### 1. The Hook (0:00 - 1:30)
* **Speaker:** "APIs are the lifeblood of modern enterprise, but bridging them to LLMs takes hours of boilerplate, Pydantic wrangling, and prompt-injection hardening. What if you could just pour a YAML file into an engine and cast a production-grade MCP server instantly?"
* **Action:** Open `specs/stripe_demo.yaml`. Briefly scroll through the Stripe spec showing the complexity (Bearer auth, nested `CustomerCreate` schemas). 
* **Speaker:** "Here is a slice of the official Stripe API. No custom MCP logic. Just raw OpenAPI."

### 2. The Execution (1:30 - 3:30)
* **Action:** Switch to terminal. Run:
  ```bash
  python forge_recipe.py -i specs/stripe_demo.yaml -o output/stripe-demo
  ```
* **Speaker:** "We're going to pass this into the Foundry. The Foundry is a multi-agent pipeline."
* **Action:** The CLI will pause at `[GATE] Plan Review`.
* **Speaker:** "First, the Architect agent parses the spec and builds a deterministic plan. Note the human-in-the-loop governance gate. We hit 'Y' to approve."
* **Action:** Type `y`. The Builder and Tester agents run. CLI pauses at `[GATE] Code Review`. Hit `y`.
* **Speaker:** "The Builder has just written Pydantic validation models, sanitized all prompt-injection vectors, and generated a local `.env.example` mapping out the Bearer tokens automatically."

### 3. The Reveal (3:30 - 6:00)
* **Action:** Open `output/stripe-demo/server/`. 
* **Speaker:** "Look what was just generated from thin air."
* **Action:** Show `validation_models.py` (highlight the strict type checking).
* **Action:** Show `audit.jsonl` and `audit_logger.py` (highlight enterprise-grade latency tracking and privacy-redacted arguments).
* **Action:** Show `test_server.py`. 
* **Speaker:** "It didn't just build the code. It built an adversarial test suite simulating prompt injections and malformed JSON-RPC attacks to prove the server is secure."

### 4. Running the Tests (6:00 - 8:00)
* **Action:** Run the generated tests in the terminal:
  ```bash
  cd output/stripe-demo/server
  python -m pytest test_server.py -v
  ```
* **Speaker:** "All tests pass instantly. The server is mathematically verified to handle malicious LLM hallucinations."

### 5. Connecting to Claude/Cursor (8:00 - 11:00)
* **Action:** Show the generated `README.md` and `run_server.bat` files.
* **Speaker:** "The final agent is the Documenter. It saw we generated a Stripe server, so it wrote this beautiful Markdown guide showing exactly how to copy the config into Claude Desktop."
* **Action:** Copy `cp .env.example .env` and paste a dummy Stripe key inside.
* **Action:** Launch the server script: `./run_server.sh`
* **Speaker:** "The server is running. We can now open Claude, ask it to 'Create a new Stripe customer for john@example.com', and it seamlessly executes the tool call through the heavily fortified Foundry environment."

---
*End of Script*
