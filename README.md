# AI Company

A framework for orchestrating autonomous AI agents as employees within a virtual company structure.

## Concept

AI Company lets you spin up a virtual organization staffed entirely by AI agents. Each agent has a role (CEO, developer, designer, QA, etc.), a personality, persistent memory, and access to real tools. Agents collaborate through structured communication, follow workflows, and produce real artifacts - code, documents, designs, and more.

## Key Features (Planned)

- **Any Company Structure** - From a 2-person startup to a 50+ enterprise, defined via config/templates
- **Deep Agent Identity** - Names, personalities, skills, seniority levels, performance tracking
- **Multi-Provider** - Anthropic Claude, OpenRouter (400+ models), local Ollama, and more via LiteLLM
- **Smart Cost Management** - Per-agent budget tracking, auto model routing, CFO agent optimization
- **Configurable Autonomy** - From fully autonomous to human-approves-everything, with a Security Ops agent in between
- **Persistent Memory** - Agents remember past decisions, code, relationships (via Mem0)
- **HR System** - Hire, fire, promote agents. HR agent analyzes skill gaps and proposes candidates
- **Real Tool Access** - File system, git, code execution, web, databases - role-based and sandboxed
- **API-First** - REST + WebSocket API with local web dashboard
- **Templates + Builder** - Pre-built company templates and interactive builder

## Status

**Design phase.** See [DESIGN_SPEC.md](DESIGN_SPEC.md) for the full high-level specification.

## Tech Stack (Planned)

- **Python 3.12+** with FastAPI, Pydantic, Typer
- **LiteLLM** for multi-provider LLM abstraction
- **Mem0** for agent memory
- **MCP** for tool integration
- **Vue 3** for web dashboard
- **SQLite** → PostgreSQL for data persistence

## Documentation

- [Design Specification](DESIGN_SPEC.md) - Full high-level design
