---
title: Agent Management
description: Hire, fire, promote, and customise agents via the REST API. Covers personality assignment, rehiring from archive, and lifecycle events.
---

# Agent Management

SynthOrg treats agents as real employees: they get hired, promoted, fired, and archived with full memory retention. This guide covers the operator-facing lifecycle: hiring an agent with a personality preset, customising their config, firing cleanly, and rehiring from the archive.

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

Partial updates via `PATCH /api/v1/agents/{name}`. Immutable fields (`id`, `hiring_date`) cannot be changed; attempting to do so returns 422.

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

What happens:

1. Active tasks are reassigned via `TaskReassignmentStrategy` (default: return to unassigned queue with priority boost).
2. Agent memories are archived to `ArchivalStore` via `MemoryArchivalStrategy` (default: full snapshot, read-only).
3. Semantic + procedural memories are selectively promoted to `OrgMemoryBackend` (rule-based).
4. Hot memory store is cleared.
5. Agent transitions to `TERMINATED`.

No data is destroyed -- just moved out of the active path.

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
// Emits: AgentHired, AgentFired, AgentPromoted, AgentDemoted, PersonalityTrimmed
```

See [Notifications & Events](notifications-and-events.md) for the full protocol.

## Setup wizard shortcuts

The setup wizard at `/api/v1/setup/*` wraps agent creation with template defaults and personality presets:

```bash
# Create an agent through the setup wizard (uses the template's default model + personality)
curl -X POST http://localhost:3001/api/v1/setup/agent \
  -H "Content-Type: application/json" \
  -H "Cookie: ${SESSION}" \
  -d '{"role": "Senior Backend Developer", "name": "Sarah Chen"}'
```

Useful during first-run; after completion, use `/api/v1/agents` for subsequent changes.

---

## See Also

- [Agent Roles & Hierarchy](agents.md) -- role catalog, seniority levels
- [Design: Agents](../design/agents.md) -- identity card, personality dimensions, identity versioning
- [Design: HR & Agent Lifecycle](../design/hr-lifecycle.md) -- full lifecycle, performance tracking, evolution
- [Security & Trust Policies](security.md) -- autonomy and tool permissions
