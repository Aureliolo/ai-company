# Roadmap

!!! warning "Work in Progress"
    SynthOrg is under active development and is **not ready for production use**.
    APIs, configuration formats, and behavior may change without notice.

## Current Status

SynthOrg is in **early development**. Substantial work has gone into the core subsystems -- provider abstraction, agent engine, security, communication, memory, tools, persistence, observability, and a web dashboard -- but the project has not yet been run end-to-end as a cohesive product.

What remains is significant: integration testing across subsystem boundaries, wiring the pieces together into coherent workflows, hardening edge cases, and validating that the system works as a whole rather than as isolated modules. The individual subsystems have unit tests and follow a consistent architecture, but the glue between them is incomplete.

Think of it as: the building blocks are shaped, but they haven't been assembled and stress-tested as a structure yet.

## What's Next

Current priorities and in-progress work are tracked on the [GitHub issue tracker](https://github.com/Aureliolo/synthorg/issues). Key areas:

- **Integration and end-to-end validation** -- wiring subsystems into working workflows
- **Security hardening** -- custom policy enforcement, sandbox network isolation
- **Human interaction layer** -- roles, access control, approval workflows
- **Production readiness** -- database backend beyond SQLite, runtime configuration, monitoring

For long-term vision (plugin system, distributed backends, inter-company communication, and more), see [Future Vision](future-vision.md).

## Tracking

All implementation work is tracked on the [GitHub issue tracker](https://github.com/Aureliolo/synthorg/issues).

## Further Reading

- [Open Questions & Risks](open-questions.md) -- unresolved design questions and identified risks
- [Future Vision](future-vision.md) -- post-MVP features and the scaling path
