# Roadmap

!!! warning "Work in Progress"
    SynthOrg is under active development and is **not ready for production use**.
    APIs, configuration formats, and behavior may change without notice.

## Current Status

SynthOrg is in **early development**. Substantial work has gone into the core subsystems -- provider abstraction, agent engine, security, communication, memory, tools, persistence, observability, and a web dashboard -- but the project has not yet been run end-to-end as a cohesive product.

What remains is significant: integration testing across subsystem boundaries, wiring the pieces together into coherent workflows, hardening edge cases, and validating that the system works as a whole rather than as isolated modules. The individual subsystems have unit tests and follow a consistent architecture, but the glue between them is incomplete.

Think of it as: the building blocks are shaped, but they haven't been assembled and stress-tested as a structure yet.

## In Progress

| Area | Description | Tracking |
|------|-------------|----------|
| **Custom security policies** | Enforce user-defined security policies and sandbox network filtering | [#610](https://github.com/Aureliolo/synthorg/issues/610) |
| **Artifact persistence** | Project and artifact storage layer | [#612](https://github.com/Aureliolo/synthorg/issues/612) |
| **Semantic conflict detection** | Workspace merge conflict detection using semantic analysis | [#611](https://github.com/Aureliolo/synthorg/issues/611) |

## Near-Term

| Area | Description | Tracking |
|------|-------------|----------|
| **Human roles and access control** | Human user types with tiered permissions | [#257](https://github.com/Aureliolo/synthorg/issues/257) |
| **Runtime sink configuration** | Add/remove/reconfigure log sinks at runtime | [#564](https://github.com/Aureliolo/synthorg/issues/564) |
| **Granular tool access** | Sub-constraints for tool permissions | [#220](https://github.com/Aureliolo/synthorg/issues/220) |
| **Web/database/terminal tools** | Essential built-in tool implementations | [#212](https://github.com/Aureliolo/synthorg/issues/212), [#213](https://github.com/Aureliolo/synthorg/issues/213), [#214](https://github.com/Aureliolo/synthorg/issues/214) |
| **Production database backend** | Move beyond SQLite for production deployments | [#210](https://github.com/Aureliolo/synthorg/issues/210) |
| **Procedural memory** | Auto-generate reusable memory from agent failures | [#420](https://github.com/Aureliolo/synthorg/issues/420) |
| **User guides** | Documentation for actual usage | [#293](https://github.com/Aureliolo/synthorg/issues/293) |

## Long-Term

These are tracked as open issues but are lower priority. See [Future Vision](future-vision.md) for the full list.

| Area | Tracking |
|------|----------|
| Plugin system | [#241](https://github.com/Aureliolo/synthorg/issues/241) |
| Multi-project support | [#242](https://github.com/Aureliolo/synthorg/issues/242) |
| External integrations (Slack, GitHub, Jira) | [#246](https://github.com/Aureliolo/synthorg/issues/246) |
| Kubernetes sandbox backend | [#219](https://github.com/Aureliolo/synthorg/issues/219) |
| Distributed message bus | [#236](https://github.com/Aureliolo/synthorg/issues/236) |
| A2A Protocol compatibility | [#235](https://github.com/Aureliolo/synthorg/issues/235) |
| GraphRAG / Temporal KG memory | [#266](https://github.com/Aureliolo/synthorg/issues/266) |
| Visual workflow editor | [#247](https://github.com/Aureliolo/synthorg/issues/247) |
| Benchmarking suite | [#248](https://github.com/Aureliolo/synthorg/issues/248) |

## Tracking

All implementation work is tracked on the [GitHub issue tracker](https://github.com/Aureliolo/synthorg/issues).

## Further Reading

- [Open Questions & Risks](open-questions.md) -- unresolved design questions and identified risks
- [Future Vision](future-vision.md) -- post-MVP features and the scaling path
