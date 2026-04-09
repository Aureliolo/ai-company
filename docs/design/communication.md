---
title: Communication
description: Message bus architecture, delegation, conflict resolution strategies, and meeting protocols for inter-agent communication.
---

# Communication

The communication architecture defines how agents exchange information, resolve
disagreements, and coordinate through structured meetings. All communication
patterns, conflict resolution strategies, and meeting protocols are pluggable
and configurable per company, per department, or per interaction type.

> **Strategic agents** (C-suite, VP, Director) receive additional anti-trendslop
> mitigation through the [Strategy module](strategy.md), which injects
> constitutional principles, multi-lens analysis, and confidence calibration
> into their system prompts.

---

## Communication Patterns

The framework supports multiple communication patterns, configurable per company:

=== "Pattern 1: Event-Driven Message Bus"

    **Recommended Default**

    ```text
    ┌──────────┐     ┌─────────────────┐     ┌──────────┐
    │  Agent A  │────>│   Message Bus   │<────│  Agent B  │
    └──────────┘     │ (Topics/Queues) │     └──────────┘
                     └────────┬────────┘
                              │
                  ┌───────────┼───────────┐
                  v           v           v
            #engineering  #product   #all-hands
            #code-review  #design    #incidents
    ```

    - Agents publish to topics, subscribe to relevant channels
    - Async by default, enables parallelism
    - Decoupled -- agents do not need to know about each other
    - Natural audit trail of all communications

    Best for
    :   Most scenarios; scales well, production-ready pattern.

=== "Pattern 2: Hierarchical Delegation"

    ```text
    CEO --> CTO --> Eng Lead --> Sr Dev --> Jr Dev
                       |
                       └--> QA Lead --> QA Eng
    ```

    - Tasks flow down the hierarchy, results flow up
    - Each level can decompose and refine tasks before delegating
    - Authority enforcement built into the flow

    Best for
    :   Structured organizations with clear chains of command.

=== "Pattern 3: Meeting-Based"

    ```text
    ┌─────────────────────────────────┐
    │        Sprint Planning          │
    │  PM + CTO + Devs + QA + Design  │
    │  Output: Sprint backlog         │
    └─────────────────────────────────┘
             │
    ┌────────┴────────┐
    │  Daily Standup  │
    │  Devs + QA      │
    │  Output: Status │
    └─────────────────┘
    ```

    - Structured multi-agent conversations at defined intervals
    - Standup, sprint planning, retrospective, design review, code review

    Best for
    :   Agile workflows, decision-making, alignment.

=== "Pattern 4: Hybrid"

    Combines all three patterns:

    - **Message bus** for async daily work and notifications
    - **Hierarchical delegation** for task assignment and approvals
    - **Meetings** for cross-team decisions and planning ceremonies

Built-in templates select the communication pattern that fits their archetype (e.g.
`event_driven` for Solo Builder, Research Lab, and Data Team, `hierarchical` for Agency,
Enterprise Org, and Consultancy, `meeting_based` for Product Studio). See the
[Company Types table](organization.md#company-types) for per-template defaults.

---

## Communication Standards

The framework aligns with emerging industry standards:

A2A Protocol (Agent-to-Agent, Linux Foundation)
:   Inter-agent task delegation, capability discovery via Agent Cards, and
    structured task lifecycle management.

MCP (Model Context Protocol, Agentic AI Foundation / Linux Foundation)
:   Agent-to-tool integration, providing standardized tool discovery and
    invocation.

---

## A2A External Gateway

The A2A gateway is an **optional** external interface that enables SynthOrg agents to
federate with agents in other A2A-compatible systems. It is disabled by default
(`a2a.enabled: false`). Internal communication is unchanged -- the MessageBus remains the
sole transport for intra-organization messages.

### Architecture

```text
                        +-----------------------+
                        |   External A2A Agent  |
                        |   (other framework)   |
                        +-----------+-----------+
                                    |
                             JSON-RPC / SSE
                                    |
+-----------------------+-----------v-----------+-----------------------+
|                       |    A2A Gateway        |                       |
|  SynthOrg             |  (optional, disabled  |                       |
|  Organization         |   by default)         |                       |
|                       +-----+-----+-----------+                       |
|                             |     |                                   |
|                      inbound|     |outbound                           |
|                             v     v                                   |
|                       +--------------------+                          |
|                       |   Message Bus      |                          |
|                       |  (internal,        |                          |
|                       |   unchanged)       |                          |
|                       +--+----+----+----+--+                          |
|                          |    |    |    |                             |
|                       +--v-+--v-+--v-+--v-+                           |
|                       | A1 | A2 | A3 | A4 |  Internal Agents          |
|                       +----+----+----+----+                           |
+-----------------------+-----------------------------------------------+
```

The gateway sits at the organization boundary and handles two directions:

Inbound (external -> internal)
:   External A2A clients discover SynthOrg agents via Agent Cards, create tasks via
    JSON-RPC, and receive updates via SSE. The gateway translates A2A requests into
    internal MessageBus messages and applies [DelegationGuard](#loop-prevention) +
    [A2A-specific security checks](operations.md#a2a-security) before admission.

Outbound (internal -> external)
:   SynthOrg agents can delegate tasks to external A2A agents. The A2A client discovers
    external agents via their Agent Card URLs, creates tasks, and maps external task
    states back to internal states.

### Agent Card Projection

When the gateway is enabled, SynthOrg serves an Agent Card at
`/.well-known/agent.json` per the A2A specification. The card is a **safe projection**
of `AgentIdentity` -- only fields relevant to external capability discovery are exposed:

| AgentIdentity Field | Agent Card Field | Included | Rationale |
|---------------------|-----------------|----------|-----------|
| `name` | `name` | Yes | Public identity |
| `role` | `description` (partial) | Yes | Capability context |
| `skills` (SkillSet) | `skills` (AgentSkill[]) | Yes | Lossless mapping via [Skill model](agents.md#skill-model) |
| `department` | metadata | Optional | Organizational context |
| `personality` | -- | No | Internal behavioral tuning |
| `level` (seniority) | -- | No | Internal authority hierarchy |
| `authority` | -- | No | Internal delegation rules |
| `model` (ModelConfig) | -- | No | Internal infrastructure |
| `tools` | -- | No | Security-sensitive capability list |
| `budget_limit` | -- | No | Internal financial data |

The proposed [Skill model](agents.md#skill-model) is A2A AgentSkill-aligned and will
enable lossless bidirectional mapping between internal skills and Agent Card capabilities.
Once implemented, importing external Agent Cards will deserialize their `AgentSkill`
objects directly into the internal `Skill` model with no field loss. Currently, skills are
string-based and require manual mapping.

### Concept Mapping

SynthOrg and A2A use different terminology for overlapping concepts. This table provides
a bidirectional reference for the gateway translation layer.

#### Task State Mapping

| SynthOrg State | A2A State | Direction | Notes |
|----------------|-----------|-----------|-------|
| `CREATED` | `submitted` | Bidirectional | Initial task creation |
| `ASSIGNED` | `working` | SynthOrg -> A2A | Agent has accepted the task |
| `IN_PROGRESS` | `working` | Bidirectional | Active execution |
| `IN_REVIEW` | `working` | SynthOrg -> A2A | Internal review stage, opaque externally |
| `BLOCKED` | `input-required` | Bidirectional | Waiting for external input |
| `SUSPENDED` | `input-required` | SynthOrg -> A2A | Approval-parked tasks |
| `INTERRUPTED` | `failed` | SynthOrg -> A2A | Interrupted execution; externally indistinguishable from failure |
| `COMPLETED` | `completed` | Bidirectional | Successful completion |
| `FAILED` | `failed` | Bidirectional | Unrecoverable failure |
| `CANCELLED` | `canceled` | Bidirectional | Client-initiated cancellation |
| `REJECTED` *(proposed)* | `rejected` | Bidirectional | Task refused by agent or guard (requires new TaskStatus value) |

**Gate verdict mapping** (not a task state):

| SynthOrg Verdict | A2A State | Direction | Notes |
|------------------|-----------|-----------|-------|
| Approval gate `ESCALATED` | `auth-required` | SynthOrg -> A2A | Gateway maps ESCALATED verdict to A2A auth-required; external client must provide additional credentials |

#### Identity Mapping

| SynthOrg | A2A | Direction | Notes |
|----------|-----|-----------|-------|
| `AgentIdentity` | `AgentCard` | SynthOrg -> A2A | One-way projection (safe subset) |
| `Skill` *(proposed)* | `AgentSkill` | Bidirectional | Lossless field correspondence (requires the enriched Skill model) |
| `SkillSet.primary` | `AgentCard.skills` (tagged `primary`) | SynthOrg -> A2A | Primary/secondary distinction preserved via tags |
| `SkillSet.secondary` | `AgentCard.skills` (tagged `secondary`) | SynthOrg -> A2A | Primary/secondary distinction preserved via tags |

#### Message and Task Lifecycle Mapping

| SynthOrg | A2A | Notes |
|----------|-----|-------|
| `Message` (internal) | `Message` + `Part[]` (A2A) | Internal message content maps to A2A text parts |
| `DelegationRequest` | `tasks/send` (JSON-RPC) | Task creation |
| `DelegationResult` | `tasks/get` response | Task completion/status |
| `TaskExecution` state | Task object + `status` | Ongoing task tracking |
| MessageBus channels | -- | No A2A equivalent; internal routing only |
| Meeting protocols | -- | No A2A equivalent; internal coordination only |

### SSE Streaming

External task update delivery uses **Server-Sent Events** per the A2A specification.
This is distinct from the internal WebSocket transport used by the dashboard:

| Consumer | Transport | Protocol | Use Case |
|----------|-----------|----------|----------|
| Web dashboard | WebSocket | Custom events | Real-time UI updates |
| External A2A client | SSE | `tasks/sendSubscribe` | Task progress streaming |

The gateway translates internal MessageBus events for subscribed tasks into SSE events
with A2A-formatted payloads. Only task-related events for explicitly subscribed tasks
are forwarded -- no internal channel traffic leaks to external consumers.

### A2A Client (Outbound)

SynthOrg agents can delegate tasks to external A2A agents through the outbound client:

1. **Discovery**: Fetch the external agent's Agent Card from its well-known URL
2. **Skill import**: Deserialize `AgentSkill[]` into internal `Skill` model (lossless)
3. **Task creation**: Send `tasks/send` JSON-RPC request with auth credentials
4. **Monitoring**: Subscribe to task updates via SSE or poll via `tasks/get`
5. **State mapping**: Map external A2A task states back to internal states (see table above)

The outbound client authenticates using the `a2a.auth.outbound` configuration (see
[A2A Security](operations.md#a2a-security)). Outbound delegations pass through the
[DelegationGuard](#loop-prevention) for loop-prevention checks (ancestry, depth,
deduplication, rate limiting, circuit breaker) before dispatch.

---

## Message Format

```json
{
  "id": "msg-uuid",
  "timestamp": "2026-02-27T10:30:00Z",
  "sender": "sarah_chen",
  "to": "engineering",
  "type": "task_update",
  "priority": "normal",
  "channel": "#backend",
  "content": "Completed API endpoint for user authentication. PR ready for review.",
  "attachments": [
    {"type": "artifact", "ref": "pr-42"}
  ],
  "metadata": {
    "task_id": "task-123",
    "project_id": null,
    "tokens_used": 1200,
    "cost_usd": 0.018,
    "extra": [["model", "example-medium-001"]]
  }
}
```

All metadata fields are nullable except `extra`, which is always present (defaults to an empty list). The `extra` field contains additional key-value pairs for extensibility.

---

## Communication Config

???+ example "Full communication configuration"

    ```yaml
    communication:
      default_pattern: "hybrid"
      message_bus:
        backend: "internal"        # internal, redis, rabbitmq, kafka
        channels:
          - "#all-hands"
          - "#engineering"
          - "#product"
          - "#design"
          - "#incidents"
          - "#code-review"
          - "#watercooler"
      meetings:
        enabled: true
        types:
          - name: "daily_standup"
            frequency: "per_sprint_day"
            participants: ["engineering", "qa"]
            duration_tokens: 2000
          - name: "sprint_planning"
            frequency: "bi_weekly"
            participants: ["all"]
            duration_tokens: 5000
          - name: "code_review"
            trigger: "on_pr"
            participants: ["author", "reviewers"]
      hierarchy:
        enforce_chain_of_command: true
        allow_skip_level: false    # can a junior message the CEO directly?
    ```

---

## Loop Prevention

Agent communication loops (A delegates to B who delegates back to A) are a
critical risk. The framework enforces multiple safeguards:

| Mechanism | Description | Default |
|-----------|-------------|---------|
| **Max delegation depth** | Hard limit on chain length (A->B->C->D stops at depth N) | 5 |
| **Message rate limit** | Max messages per agent pair within a time window | 10 per minute |
| **Identical request dedup** | Detects and rejects duplicate task delegations within a window | 60s window |
| **Circuit breaker** | If an agent pair exceeds error/bounce threshold, block further messages until manual reset or cooldown | 3 bounces, 5min cooldown |
| **Task ancestry tracking** | Every delegated task carries its full delegation chain; agents cannot delegate back to any ancestor in the chain | Always on |

???+ example "Loop prevention configuration"

    ```yaml
    loop_prevention:
      max_delegation_depth: 5
      rate_limit:
        max_per_pair_per_minute: 10
        burst_allowance: 3
      dedup_window_seconds: 60
      circuit_breaker:
        bounce_threshold: 3
        cooldown_seconds: 300
    ```

    Ancestry tracking is always enabled and is not user-configurable.

When a loop is detected, the framework:

1. Blocks the looping message
2. Notifies the sending agent with the detected loop chain
3. Escalates to the sender's manager (or human if at top of hierarchy)
4. Logs the loop for analytics and process improvement

---

## Conflict Resolution Protocol

When two or more agents disagree on an approach (architecture, implementation,
priority), the framework provides multiple configurable resolution strategies
behind a `ConflictResolver` protocol. New strategies can be added without
modifying existing ones. The strategy is configurable per company, per
department, or per conflict type.

=== "Strategy 1: Authority + Dissent Log"

    **Default Strategy**

    The agent with higher authority level decides. Cross-department conflicts
    (incomparable authority) escalate to the lowest common manager in the
    hierarchy. The losing agent's reasoning is preserved as a **dissent record**
    -- a structured log entry containing the conflict context, both positions,
    and the resolution. Dissent records feed into organizational learning and
    can be reviewed during retrospectives.

    ```yaml
    conflict_resolution:
      strategy: "authority"            # authority, debate, human, hybrid
    ```

    - Deterministic, zero extra tokens, fast resolution
    - Dissent records create institutional memory of alternative approaches

=== "Strategy 2: Structured Debate + Judge"

    Both agents present arguments (1 round each). A judge -- their shared
    manager, the CEO, or a configurable arbitrator agent -- evaluates both
    positions and decides. The judge's reasoning and both arguments are logged
    as a dissent record.

    ```yaml
    conflict_resolution:
      strategy: "debate"
      debate:
        judge: "shared_manager"        # shared_manager, ceo, designated_agent
    ```

    - Better decisions -- forces agents to articulate reasoning
    - Higher token cost, adds latency proportional to argument length

=== "Strategy 3: Human Escalation"

    All genuine conflicts go to the human approval queue with both positions
    summarized. The agent(s) park the conflicting task and work on other tasks
    while waiting (see [Approval Timeout](operations.md#approval-timeout-policy)).

    ```yaml
    conflict_resolution:
      strategy: "human"
    ```

    - Safest -- human always makes the call
    - Bottleneck at scale, depends on human availability

=== "Strategy 4: Hybrid"

    **Recommended for Production**

    Combines strategies with an intelligent review layer:

    1. Both agents present arguments (1 round) -- preserving dissent
    2. A **conflict review agent** evaluates the result:
        - If the resolution is **clear** (one position is objectively better,
          or authority applies cleanly) -- resolve automatically, log dissent
          record
        - If the resolution is **ambiguous** (genuine trade-offs, no clear
          winner) -- escalate to human queue with both positions + the review
          agent's analysis

    ```yaml
    conflict_resolution:
      strategy: "hybrid"
      hybrid:
        review_agent: "conflict_reviewer"  # dedicated agent or role
        escalate_on_ambiguity: true
    ```

    - Best balance: most conflicts resolve fast, humans only see genuinely
      hard calls
    - Most complex to implement; review agent itself needs careful prompt
      design

---

## Meeting Protocol

Meetings (Pattern 3 above) follow configurable protocols that determine how
agents interact during structured multi-agent conversations. Different meeting
types naturally suit different protocols. All protocols implement a
`MeetingProtocol` protocol, making the system extensible -- new protocols can be
registered and selected per meeting type. Cost bounds are enforced by
`duration_tokens` in the [communication config](#communication-config).

=== "Protocol 1: Round-Robin Transcript"

    The meeting leader calls each participant in turn. A shared transcript
    grows as each agent responds, seeing all prior contributions. The leader
    summarizes and extracts action items at the end.

    ```yaml
    meeting_protocol: "round_robin"
    round_robin:
      max_turns_per_agent: 2
      max_total_turns: 16
      leader_summarizes: true
    ```

    - Simple, natural conversation feel, each agent sees full context
    - Token cost grows quadratically; last speaker has more context (ordering
      bias)

    Best for
    :   Daily standups, status updates, small groups (3--5 agents).

=== "Protocol 2: Async Position Papers + Synthesizer"

    Each agent independently writes a short position paper (parallel execution,
    no shared context). A synthesizer agent reads all positions, identifies
    agreements and conflicts, and produces decisions + action items.

    ```yaml
    meeting_protocol: "position_papers"
    position_papers:
      max_tokens_per_position: 300
      synthesizer: "meeting_leader"    # who synthesizes
    ```

    - Cheapest -- parallel calls, no quadratic growth, no ordering bias, no
      groupthink
    - Loses back-and-forth dialogue; agents cannot challenge each other's ideas

    Best for
    :   Brainstorming, architecture proposals, large groups, cost-sensitive
        meetings.

=== "Protocol 3: Structured Phases"

    Meeting split into phases with targeted participation:

    1. **Agenda broadcast** -- leader shares agenda and context to all
       participants
    2. **Input gathering** -- each agent submits input independently (parallel)
    3. **Discussion round** -- only triggered if conflicts are detected between
       inputs; relevant agents debate (1 round, capped tokens)
    4. **Decision + action items** -- leader synthesizes, creates tasks from
       action items

    ```yaml
    meeting_protocol: "structured_phases"
    auto_create_tasks: true              # action items become tasks (top-level, applies to any protocol)
    structured_phases:
      skip_discussion_if_no_conflicts: true
      max_discussion_tokens: 1000
    ```

    - Cost-efficient -- parallel input, discussion only when needed
    - More complex orchestration; conflict detection between inputs adds
      implementation complexity

    Best for
    :   Sprint planning, design reviews, architecture decisions.

## Meeting Scheduler

The `MeetingScheduler` is a background service that bridges meeting configuration
and execution. It reads `MeetingsConfig` and manages two modes of meeting
triggering:

### Frequency-Based Scheduling

Meetings with a `frequency` field (e.g. `daily`, `weekly`, `bi_weekly`,
`per_sprint_day`, `monthly`) are scheduled as periodic asyncio tasks. The
`MeetingFrequency` enum maps each value to a sleep interval in seconds. Periodic
tasks survive transient errors -- a single execution failure does not kill the
background loop.

### Event-Triggered Meetings

Meetings with a `trigger` field (e.g. `on_pr`, `deploy_complete`) are executed
on demand via `trigger_event(event_name, context)`. The scheduler matches all
meeting types whose `trigger` value equals the event name and executes them in
parallel using `asyncio.TaskGroup`.

### Participant Resolution

The `ParticipantResolver` protocol resolves participant reference strings from
config into concrete agent IDs. The `RegistryParticipantResolver` implementation
uses the `AgentRegistryService` with a five-step cascade:

1. **Context lookup** -- if the event context dict has a matching key, use its value.
2. **Special `"all"`** -- resolves to all active agents.
3. **Department lookup** -- resolves to all agents in the named department.
4. **Agent name lookup** -- resolves to the agent with that name.
5. **Pass-through** -- assumes the entry is a literal agent ID.

Results are deduplicated while preserving insertion order. The first resolved
participant is designated as the meeting leader.

When no `AgentRegistryService` is available (e.g. during auto-wiring without an
explicit registry), the `PassthroughParticipantResolver` is used as a fallback.
It supports only context lookup and literal pass-through (steps 1 and 5 above),
skipping the registry-dependent steps (2--4).

### Meeting API Response Enrichment

The meeting REST API enriches every `MeetingRecord` response with computed
analytics fields. Per-participant metrics are derived from
`MeetingMinutes.contributions`:

- **`token_usage_by_participant`** (`dict[str, int]`): total tokens (input +
  output) consumed per agent. Empty when no minutes are available.
- **`contribution_rank`** (`tuple[str, ...]`): agent IDs sorted by total token
  usage descending. Empty when no minutes are available.

Duration is computed from the meeting timestamps, not from contributions:

- **`meeting_duration_seconds`** (`float | null`, `>= 0.0`): duration computed
  from `ended_at - started_at`, clamped to `0.0` when negative. `null` when no
  minutes are available.

These fields are applied to all meeting endpoints (list, detail, trigger).

### Auto-Wiring

The `MeetingOrchestrator` and `MeetingScheduler` are auto-wired at startup
alongside Phase 1 services (no persistence dependency). All three meeting
protocols are registered with default configs. A stub `agent_caller` returns
empty `AgentResponse` instances, making the meeting endpoints structurally
available (no 503 on listing) while actual agent invocation requires a
coordinator to be explicitly provided.

---

## Multi-Agent Failure Pattern Guardrails

*Research findings from #690. See also: `docs/research/multi-agent-failure-audit.md`.*

Empirical data (CIO, 2026) shows swarm topologies fail at 68% vs. 36% for hierarchical
orchestration. SynthOrg's orchestrated approach is validated, but the same failure modes
emerge if agent boundaries are poorly managed. This section documents current guardrails
and known risks.

### Meeting Protocol Safety

All three meeting protocols (StructuredPhases, RoundRobin, PositionPapers) guarantee
bounded execution via `TokenTracker` phase-boundary checks, hard token budgets with 20%
synthesis reserve, and turn/round limits. No protocol has unbounded execution paths.

**Meeting-task feedback loop mitigation**: `MeetingProtocolConfig.auto_create_tasks`
defaults to `True`. Two guardrails prevent runaway task/meeting cycles:
`MeetingTypeConfig.min_interval_seconds` enforces per-type cooldown on event-triggered
meetings, and `MeetingProtocolConfig.max_tasks_per_meeting` caps task creation from
action items. See #1115.

### Conflict Resolution Termination

All four conflict resolution strategies terminate with bounded resource use:

- **AuthorityResolver**: Deterministic seniority comparison. Always terminates; no LLM calls.
- **DebateResolver**: Single LLM judge call (one-shot, no retry loop). Falls back to
  Authority if no evaluator configured, or if the evaluator raises an exception (#1117).
- **HumanEscalationResolver**: Returns `ESCALATED_TO_HUMAN` immediately. **Stub
  implementation** pending #37 -- no actual blocking for human input yet.
- **HybridResolver**: Single LLM review call; deterministic fallback to Authority on ambiguity.

### Delegation Guard

Five mechanisms protect against swarm drift (`communication/loop_prevention/guard.py`):

1. Ancestry check (cycle prevention)
2. Max delegation depth (default 5)
3. Content deduplication (60s window)
4. Per-pair rate limiting (10/min)
5. Circuit breaker (3 bounces, exponential backoff cooldown capped at `max_cooldown_seconds`)

Circuit breaker uses exponential backoff: `cooldown = base * 2^(trip_count - 1)`,
capped at `max_cooldown_seconds` (default 3600s). On cooldown expiry, the bounce count
resets but the trip count is preserved, so successive trips produce progressively longer
cooldowns (#1116). Circuit breaker state (trip count, bounce count) is persisted to SQLite
via `CircuitBreakerStateRepository` so guardrails survive restarts. Dedup window and rate
limiter remain in-memory (short-lived by design).

### Microservices Anti-Patterns: Assessment

| Pattern | SynthOrg Risk | Mitigation |
|---|---|---|
| Chatty interfaces | Low -- detected via `MessageOverhead.is_quadratic` | Detection exists; no enforcement circuit breaker |
| Distributed monolith | None -- async pull message bus, no synchronous coupling | |
| Ownership ambiguity | None -- TaskEngine single-writer actor | |
| Cascading failure | Low -- `fail_fast` bounds wave propagation | No upstream contamination detection |
