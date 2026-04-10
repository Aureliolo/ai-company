# Future Vision

These features represent the longer-term direction for SynthOrg beyond the current development cycle.

## Planned Features

| Feature | Version | Status |
|---------|---------|--------|
| Plugin system | v0.7 | Planned |
| Multi-project support | v0.8 | Planned |
| Benchmarking suite | v0.7 | Planned |
| Community template marketplace | v0.7 | Research |
| Agent evolution (learning from feedback) | v0.7 | Planned |
| Training mode (learn from senior agents) | v0.7 | Planned |
| Client simulation | v0.7 | Planned |
| Inter-company communication | v0.7 | Planned |
| A2A protocol compatibility | v0.7 | Research |
| Dynamic company scaling | v0.8 | Planned |
| Self-improving company | v0.8 | Planned |
| Distributed message bus | v0.8 | Planned |
| Distributed task queue | v0.8 | Planned |
| PostgreSQL persistence backend | v0.8 | Planned |
| Shift system for agents | v0.8 | Planned |

## Recently Shipped (formerly "Future")

These features were previously listed as future work and have since been implemented:

- **Visual workflow editor** -- shipped in v0.5.9 (PR #1018)
- **Network hosting / multi-user access** -- shipped in v0.5.9 (PR #1032)
- **Workflow execution from graph definitions** -- shipped in v0.6.0 (PR #1040)
- **Local model management** (Ollama/LM Studio) -- shipped in v0.6.0 (PR #1037)
- **Ceremony scheduling** (8 strategies) -- shipped across v0.5.5--v0.5.7
- **Agent promotions** -- core promotion/demotion system shipped in v0.5.0

## Scaling Path

SynthOrg is designed to scale incrementally from a local single-process deployment to a hosted platform.

```text
Phase 1: Local Single-Process (current)
  -- Async runtime, SQLite, in-memory bus, 1-10 agents

Phase 2: Local Multi-Process (v0.7-v0.8)
  -- External message bus, production DB, sandboxed execution, 10-30 agents
  -- See the [Distributed Runtime](../design/distributed-runtime.md) page for
     the NATS JetStream backend and distributed task queue

Phase 3: Network/Server (v0.8+)
  -- Full API with multi-user auth, distributed agents, 30-100 agents

Phase 4: Cloud/Hosted (future)
  -- Container orchestration, horizontal scaling, marketplace, 100+ agents
```

Each phase builds on the previous one. The pluggable protocol interfaces throughout the codebase (persistence, memory, message bus, sandbox) are designed to make these transitions configuration changes rather than rewrites.
