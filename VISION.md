# MCP Server Foundry — Product Vision

This document details the long-term strategic direction, defensive moats, and business tier models for the MCP Server Foundry.

## Regulated Industry Compliance Adapters (Future MOAT)
We plan to build domain-specific compliance adapters for highly regulated industries:
- **Finance**: AML (Anti-Money Laundering) checks, transaction monitoring, and financial services compliance adapters.
- **Healthcare**: FHIR (Fast Healthcare Interoperability Resources) and HL7 adapters.
- **Privacy**: Automated GDPR and HIPAA verification layers.

## Public Recipe Library Network Effect
A public, community-driven recipe library containing pre-validated configurations for popular global APIs:
- Stripe
- Salesforce
- GitHub
- Jira
- HubSpot

## Cryptographic ProvenanceManifest
 verifying generation provenance using cryptographically signed packages containing:
- SHA-256 hashes of the original OpenAPI input spec
- Exact Forge and agent pipeline versions
- Full execution trace for compliance audit logs

## Defensive Moats
1. **Data Flywheel**: Continuous tuning of templates based on generated gateway errors and validation failures.
2. **High Switching Costs**: Seamless CI/CD integration automatically triggers gateway regeneration upon upstream spec commits.
3. **Certified Badging**: MCP Forge Certified badges serve as trust signals for third-party client integrations.

## Business Tiers & Pricing Model

| Tier | Price | Scope |
|---|---|---|
| **Open Core** | Free | Single Data Agent runtime, community recipes, local generation runs |
| **Pro / Teams** | $49–$199/mo | Private recipe vaults, CI/CD pipeline connectors, hosted regeneration loops |
| **Enterprise** | Custom | Regulated adapters (AML, FHIR, GDPR), cryptographic provenance tracing, custom SLAs, on-prem setups |

***

## Acknowledgments
Built with [IBM Bob](https://www.ibm.com/bob) — the agentic orchestrator that makes this four-agent compiler pipeline possible.
Exposes standard interfaces utilizing the [Model Context Protocol](https://modelcontextprotocol.io/) open specification.
