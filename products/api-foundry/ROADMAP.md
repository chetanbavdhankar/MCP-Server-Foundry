# API Foundry — Development Roadmap

This document outlines the planned future milestones and high-tier architectural features for the API Foundry.

## Unimplemented / Planned Features

### 1. Semgrep Build Gate
- **Status**: Deferred / Backlog.
- **Concept**: Run custom Semgrep checks against generated servers during compilation to ensure no dangerous python imports or mutating query operations bypass standard handlers.

### 2. Adversarial Test Suite Generation
- **Status**: Deferred / Backlog.
- **Concept**: Utilize reasoning-heavy models (e.g. Claude Sonnet) to generate deep adversarial inputs (SQL injection payloads, prompt injection vectors, shell bypass attempts) custom-tailored to the API's fields.

### 3. Cryptographic Provenance Manifest
- **Status**: Deferred / Backlog.
- **Concept**: Sign generated packages with SHA-256 signatures, including Forge versioning, time-stamping, and model routing configuration, to allow third-party verification in highly regulated environments.

### 4. HTTP Transport Support
- **Status**: Deferred / Backlog.
- **Concept**: Expose an `--transport http` CLI launch switch to run the server on standard HTTP ports instead of standard Stdio loop streams.

### 5. Multi-Model Routing
- **Status**: Deferred / Backlog.
- **Concept**: Route pipeline sub-tasks (parsing, codegen, testing) to different provider configurations via a `providers.yaml` dashboard.
