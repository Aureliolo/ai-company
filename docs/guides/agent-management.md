---
title: Agent Management
description: Hire, fire, promote, and customize agents via the REST API. Covers personality assignment, rehiring from archive, and lifecycle events.
---

# Agent Management

SynthOrg treats agents as real employees: they get hired, promoted, fired, and archived with full memory retention. This guide covers the operator-facing lifecycle: hiring an agent with a personality preset, customizing their config, firing cleanly, and rehiring from the archive.

For the architecture (identity versioning, evolution, five-pillar evaluation), see [Agents](../design/agents.md) and [HR & Agent Lifecycle](../design/hr-lifecycle.md).

---

## Hiring

Agents are hired via `POST /api/v1/agents`. You need a name, role, department, seniority level, and either an explicit model or a tier (`large`/`medium`/`small`) that the model matcher resolves against your configured providers.

### From a personality preset

```bash
# List available presets (built-in + custom)
curl http://localhost:3001/api/v1/personalities/presets \
  -H "Cookie: ${SESSION}" | jq '.data[] | {name, description}'

# Hire with a preset
curl -X POST http://localhost:3001/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{
    "name": "Sarah Chen",
    "role": "Senior Backend Developer",
    "department": "Engineering",
    "level": "Senior",
    "personality_preset": "analytical-pragmatist",
    "model_tier": "medium"
  }' | jq
```

### With explicit personality config

```bash
curl -X POST http://localhost:3001/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{
    "name": "Alex Rivera",
    "role": "QA Engineer",
    "department": "Quality",
    "level": "Mid",
    "model_tier": "small",
    "personality": {
      "traits": ["thorough", "skeptical"],
      "communication_style": "precise",
      "openness": 0.5,
      "conscientiousness": 0.95,
      "extraversion": 0.4,
      "agreeableness": 0.6,
      "stress_response": 0.7,
      "decision_making": "analytical",
      "collaboration": "team",
      "verbosity": "balanced",
      "conflict_approach": "collaborate"
    }
  }' | jq
```

### With tool and autonomy overrides

```bash
curl -X POST http://localhost:3001/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{
    "name": "Morgan Taylor",
    "role": "DevOps Engineer",
    "department": "Engineering",
    "level": "Senior",
    "model_tier": "medium",
    "autonomy_level": "semi",
    "tools": {
      "access_level": "elevated",
      "allowed": ["file_system", "git", "terminal", "deployment"],
      "denied": []
    }
  }' | jq
```

## Updating an agent

Partial updates via `PATCH /api/v1/agents/{name}`. The server validates conflicts and domain constraints (e.g. duplicate names, missing departments); consult the OpenAPI schema for the exact accepted fields and response codes.

```bash
# Change model tier
curl -X PATCH http://localhost:3001/api/v1/agents/${AGENT_NAME} \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"model_tier": "large"}'

# Change autonomy
curl -X PATCH http://localhost:3001/api/v1/agents/${AGENT_NAME} \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"autonomy_level": "supervised"}'

# Swap personality preset
curl -X PATCH http://localhost:3001/api/v1/agents/${AGENT_NAME} \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"personality_preset": "creative-explorer"}'
```

Every update creates a new `AgentIdentity` version snapshot in `agent_identity_versions`. Query the history:

```bash
curl http://localhost:3001/api/v1/agents/${AGENT_ID}/versions \
  -H "Cookie: ${SESSION}" | jq '.data[] | {version, content_hash, saved_by, saved_at}'

# Diff two versions
curl "http://localhost:3001/api/v1/agents/${AGENT_ID}/versions/diff?from_version=1&to_version=3" \
  -H "Cookie: ${SESSION}" | jq '.data.field_changes[] | {field_path, change_type, old_value, new_value}'

# Rollback
curl -X POST http://localhost:3001/api/v1/agents/${AGENT_ID}/versions/rollback \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"target_version": 1, "reason": "v2 overshot on autonomy"}' | jq
```

## Firing

Firing is a CRITICAL-risk operation requiring human approval by default. The pruning service can also propose fires based on performance trends.

```bash
curl -X DELETE http://localhost:3001/api/v1/agents/${AGENT_NAME} \
  -H "Cookie: ${SESSION}"
```

The `DELETE /api/v1/agents/{agent_name}` endpoint does not accept a request body. Approval metadata (reason, justification) is recorded separately when the `CRITICAL`-risk approval gate captures the decision.

Current behavior (`delete_agent` in `src/synthorg/api/services/_org_agent_mutations.py`):

1. The API validates the agent exists and runs org-mutation guard checks.
2. The agent record is removed from the active org configuration.
3. A company snapshot is persisted and an `API_AGENT_DELETED` event is logged and broadcast on the `agents` WebSocket channel.

Planned (not yet implemented): automated task reassignment via `TaskReassignmentStrategy`, memory archival via `MemoryArchivalStrategy`, selective promotion to `OrgMemoryBackend`, and an explicit `TERMINATED` lifecycle state. Until those land, fires are best paired with manual task reassignment before the DELETE call.

## Rehiring from archive

```bash
# List archived agents
curl "http://localhost:3001/api/v1/agents?status=terminated" \
  -H "Cookie: ${SESSION}" | jq

# Rehire -- restores archived memory into a new identity
curl -X POST http://localhost:3001/api/v1/agents/${AGENT_NAME}/rehire \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"department": "Engineering", "level": "Senior"}' | jq
```

The rehired agent gets a fresh identity (new hire date, new version chain) but inherits their archived memories.

## Lifecycle events (WebSocket)

Subscribe to the `agents` channel to get real-time lifecycle events:

```javascript
ws.send(JSON.stringify({ action: 'subscribe', channel: 'agents' }))
// Emits WsEventType values (see src/synthorg/api/ws_models.py):
//   agent.created, agent.updated, agent.deleted,
//   agent.hired, agent.fired, agent.status_changed,
//   personality.trimmed
```

See [Notifications & Events](notifications-and-events.md) for the full protocol.

## Setup wizard shortcuts

`/api/v1/setup/*` is the first-run wizard. Template-based auto-creation happens at `POST /api/v1/setup/company` when a template is selected; the wizard hydrates the org with the template's default agents in one shot. For the "Start Blank" path, `POST /api/v1/setup/agent` creates a single agent with an explicit model assignment:

```bash
# Create one agent on the Start Blank path; model assignment is required.
curl -X POST http://localhost:3001/api/v1/setup/agent \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{
    "role": "Senior Backend Developer",
    "name": "Sarah Chen",
    "model_provider": "example-provider",
    "model_id": "example-medium-001"
  }'
```

After the wizard completes, use `/api/v1/agents` for subsequent changes.

---

## See Also

- [Agent Roles & Hierarchy](agents.md) -- role catalog, seniority levels
- [Design: Agents](../design/agents.md) -- identity card, personality dimensions, identity versioning
- [Design: HR & Agent Lifecycle](../design/hr-lifecycle.md) -- full lifecycle, performance tracking, evolution
- [Security & Trust Policies](security.md) -- autonomy and tool permissions
