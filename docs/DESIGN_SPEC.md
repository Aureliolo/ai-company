# SynthOrg - High-Level Design Specification

> A framework for building synthetic organizations -- autonomous AI agents orchestrated as a virtual company, with configurable roles, hierarchies, communication patterns, and tool access.

---

The design specification has been split into focused documentation pages for better navigation and maintainability. Each page covers a cohesive domain of the framework's design.

## Design Pages

| Page | Sections | Description |
|------|----------|-------------|
| [Design Overview](design/index.md) | Vision, Core Concepts | What SynthOrg is, design principles, glossary |
| [Agents & HR](design/agents.md) | Agent System, HR | Agent identity, roles, hiring, performance, evaluation, promotions |
| [Organization & Templates](design/organization.md) | Company Structure, Templates | Company types, hierarchy, departments, template system |
| [Communication](design/communication.md) | Communication Architecture | Message bus, delegation, conflict resolution, meetings |
| [Task & Workflow Engine](design/engine.md) | Task Engine | Task lifecycle, execution loops, routing, recovery, shutdown, workflow definitions, blueprints, versioning, workflow execution |
| [Memory & Persistence](design/memory.md) | Memory & Persistence | Memory types, backends, retrieval, operational data |
| [Multi-Agent Memory Consistency](design/memory-consistency.md) | Consistency Model | Append-only writes, MVCC snapshot reads, conflict handling, deployment rollout |
| [Semantic Ontology](design/ontology.md) | Entity Definitions, Versioning, Drift | Shared vocabulary, decorator, backend, bootstrap, drift detection |
| [Operations](design/operations.md) | Providers, Budget, Tools, Security, Human Interaction | Provider layer, cost management, sandboxing, security, API |
| [Brand Identity & UX](design/brand-and-ux.md) | Brand, Themes, Colors, Typography, Density, Animation | Visual identity, semantic color system, theme architecture |
| [Page Structure & IA](design/page-structure.md) | Pages, Navigation, Routing, WebSocket, Responsive | Page list, sidebar hierarchy, URL routing map, WS subscriptions |
| [UX Design Guidelines](design/ux-guidelines.md) | Color System, Components, Interaction, Animation, Accessibility, Responsive | Implementable specs for all v0.5.0 dashboard pages |
| [UX Research](design/ux-research.md) | Framework Decision, Migration | Vue-to-React evaluation, decision rationale, migration timeline |
| [Ceremony Scheduling](design/ceremony-scheduling.md) | Strategies, Protocols, Velocity | Pluggable ceremony scheduling, 8 strategies, velocity calculation |
| [Strategy & Trendslop Mitigation](design/strategy.md) | Lenses, Principles, Confidence, Impact | Anti-trendslop mitigation for strategic agents |

## Supporting Pages

| Page | Description |
|------|-------------|
| [Tech Stack](architecture/tech-stack.md) | Technology choices and engineering conventions |
| [Decision Log](architecture/decisions.md) | All design decisions, organized by domain |
| [Research & Prior Art](reference/research.md) | Framework comparison and scaling research |
| [Industry Standards](reference/standards.md) | MCP, A2A, and other standards |
| [ACG Glossary](architecture/acg-glossary.md) | Bidirectional ACG-to-SynthOrg concept mapping |
| [Open Questions & Risks](roadmap/open-questions.md) | Unresolved questions and risk mitigations |
| [Future Vision](roadmap/future-vision.md) | Backlog features and scaling path |
