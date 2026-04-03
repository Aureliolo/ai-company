# Roadmap

## Current Status

SynthOrg is in **active development** at v0.6.x. The core subsystems are built, tested (13,000+ unit tests, 80%+ coverage), and integrated through a REST + WebSocket API, React 19 dashboard, and Go CLI.

What works today:

- **Agent engine** with ReAct, Plan-and-Execute, Hybrid execution loops, crash recovery, and task decomposition
- **Budget & cost management** with per-agent limits, auto-downgrade, spending reports, and anomaly detection
- **Security** with fail-closed rule engine, 5 autonomy tiers, progressive trust, output scanning, and audit logging
- **Memory** with hybrid retrieval (dense + BM25 sparse), tool-based injection, procedural memory auto-generation from failures, and consolidation
- **Communication** with message bus, delegation, conflict resolution, and meeting protocols
- **Workflow engine** with Kanban, Agile sprints, ceremony scheduling (8 strategies), visual workflow editor, and workflow execution from graph definitions
- **Web dashboard** (React 19 + shadcn/ui) with org chart, task board, agent detail, budget tracking, provider management, workflow editor, ceremony policy settings, and setup wizard
- **CLI** (Go) with init, start, stop, doctor, config, wipe, cleanup, and cosign/SLSA verification
- **Docker deployment** with Chainguard distroless images, Trivy + Grype scanning, and cosign signatures
- **Multi-user access** with JWT auth, session management, and concurrent access handling
- **Local model management** for Ollama and LM Studio (browse, pull, delete, configure launch parameters)

What's not there yet:

- **End-to-end production runs** -- subsystems are integrated but the full autonomous loop (agents receiving work, executing, producing artifacts, iterating) has not been validated as a cohesive product
- **PostgreSQL persistence** -- SQLite only (planned for v0.8)
- **Distributed backends** -- message bus, task queue, and persistence are local-process only (planned for v0.8)
- **Tool ecosystem** -- built-in tools cover file system, git, sandbox, and MCP bridge; web, database, terminal, and other tool categories are planned for v0.7

## What's Next

All work is tracked on the [GitHub issue tracker](https://github.com/Aureliolo/synthorg/issues) with version labels (`v0.6`, `v0.6.2`, etc.).

### v0.6 (current) -- Workflows, Memory, Providers

- Capability-aware prompt profiles for model tier adaptation
- Workflow execution lifecycle (COMPLETED/FAILED transitions)
- Workflow editor improvements (list page, YAML import, conditionals, minimap, copy/paste)
- Procedural memory auto-generation from agent failures
- Quality scoring Layers 2+3 (LLM judge + human override)
- Fine-tuning pipeline for embedding models
- Memory consolidation upgrades (LLM Merge, Search-and-Ask)
- Coordination metrics pipeline
- Automated reporting system

### v0.7 -- Tools, Security, Research

- Sandbox security improvements (auth proxy, gVisor, Chainguard packages)
- Core tool categories (web, database, terminal/shell)
- Advanced memory research (GraphRAG, consistency protocols, RL consolidation)
- Safety classifier for approval gates
- Hallucination detection
- Plugin system, benchmarking suite, A2A protocol compatibility

### v0.8 -- Production Hardening

- PostgreSQL persistence backend
- Distributed message bus and task queue
- Dynamic company scaling
- Multi-project support

See [Future Vision](future-vision.md) for the longer-term direction and [Open Questions](open-questions.md) for unresolved design decisions.
