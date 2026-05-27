# Foundry Hackathon Demo: 4-Minute Regeneration

**Objective:** Prove that the Foundry eliminates technical debt by making iteration zero-friction. When an API changes, the MCP server shouldn't require manual refactoring—it should just be regenerated.

## ⏱️ Prep
1. Ensure the `output/stripe-demo/` folder already exists from the first demo.
2. Have `specs/stripe_demo.yaml` ready to edit.

## 🎬 The Demo (4 Minutes)

### 1. The Scenario (0:00 - 1:00)
* **Speaker:** "APIs change. Stripe adds a new 'Refunds' endpoint. GitHub changes a parameter. Historically, your engineering team would have to open the MCP server, update the Pydantic models, rewrite the handlers, and pray they didn't break existing tests."
* **Speaker:** "With the Foundry, the spec *is* the source of truth."

### 2. The Mutation (1:00 - 2:00)
* **Action:** Open `specs/stripe_demo.yaml`. 
* **Action:** Add a quick new endpoint at the bottom of the `paths` block:
```yaml
  /refunds:
    post:
      summary: Create a refund
      tags:
        - Refunds
      responses:
        '200':
          description: Refund created.
```
* **Speaker:** "We've just added a new Refunds endpoint to our YAML. That's all we do as developers."

### 3. The Regeneration (2:00 - 3:30)
* **Action:** Switch to terminal and re-run the pipeline with the CI/CD bypass flag:
  ```bash
  python forge_recipe.py -i specs/stripe_demo.yaml -o output/stripe-demo --auto-approve
  ```
* **Speaker:** "We pass `--auto-approve` to simulate a CI/CD pipeline. The agents re-architect the plan, re-generate the entire codebase, and append the new `create_a_refund` tool."

### 4. The Verification (3:30 - 4:00)
* **Action:** Open `output/stripe-demo/server/validation_models.py` to see the new schemas.
* **Action:** Run the tests:
  ```bash
  cd output/stripe-demo/server
  python -m pytest test_server.py -v
  ```
* **Speaker:** "The test suite was re-generated, and the tests pass. We didn't touch a single line of Python. That is the power of deterministic agentic generation."

---
*End of Script*
