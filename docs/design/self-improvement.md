# Self-Improving Company

The self-improvement meta-loop observes company-wide signals from 7 existing subsystems and produces deployment-level improvement proposals through a rule-first hybrid pipeline with mandatory human approval.

## Architecture Overview

The meta-loop operates at the **company altitude** (distinct from per-agent evolution in #243) and follows the pluggable protocol + strategy + factory + config discriminator pattern used throughout SynthOrg.

```mermaid
flowchart TD
    subgraph signals["Signal Aggregation (7 domains)"]
        P[Performance]
        B[Budget]
        C[Coordination]
        S[Scaling]
        E[Errors]
        V[Evolution]
        T[Telemetry]
    end

    signals --> SNAP[OrgSignalSnapshot]
    SNAP --> RE[Rule Engine<br/>9 built-in rules]
    RE -->|rules fire| STRAT[Strategies<br/>Config / Architecture / Prompt]
    STRAT --> GUARD[Guard Chain<br/>Scope / Rollback / Rate / Approval]
    GUARD -->|all pass| QUEUE[Approval Queue<br/>Human Review]
    QUEUE -->|approved| ROLLOUT[Rollout<br/>Before-After / Canary]
    ROLLOUT --> REGRESS[Regression Detection<br/>Threshold + Statistical]
    REGRESS -->|regression| ROLLBACK[Auto-Rollback]
    REGRESS -->|no regression| APPLIED[Applied]
```

## Package Structure

```text
src/synthorg/meta/
  models.py            -- ImprovementProposal, RollbackPlan, OrgSignalSnapshot, etc.
  protocol.py          -- SignalAggregator, ImprovementStrategy, ProposalGuard, etc.
  config.py            -- SelfImprovementConfig (frozen, safe defaults)
  service.py           -- SelfImprovementService orchestrator
  factory.py           -- Component construction from config

  rules/               -- Signal pattern detection
    engine.py          -- RuleEngine (evaluates rules, sorts by severity)
    builtin.py         -- 9 built-in rules with configurable thresholds

  strategies/          -- Proposal generation
    config_tuning.py   -- Config field changes
    architecture.py    -- Structural changes (roles, workflows)
    prompt_tuning.py   -- Org-wide constitutional principles

  signals/             -- Signal aggregation from existing subsystems
    performance.py     -- PerformanceTracker wrapper
    budget.py          -- Budget analytics wrapper
    coordination.py    -- Coordination metrics wrapper
    scaling.py         -- ScalingService wrapper
    errors.py          -- Classification pipeline wrapper
    evolution.py       -- EvolutionService wrapper
    telemetry.py       -- Telemetry pipeline wrapper
    snapshot.py        -- Parallel snapshot builder

  guards/              -- Proposal validation chain
    scope_check.py     -- Altitude scope enforcement
    rollback_plan.py   -- Rollback plan validation
    rate_limit.py      -- Submission rate limiting
    approval_gate.py   -- Mandatory human approval routing

  rollout/             -- Staged deployment
    before_after.py    -- Whole-org with observation window
    canary.py          -- Canary subset with expansion
    rollback.py        -- Rollback plan executor
    regression/        -- Tiered detection
      threshold.py     -- Layer 1: instant circuit-breaker
      statistical.py   -- Layer 2: Welch's t-test
      composite.py     -- Combines both layers

  appliers/            -- Change execution
    config_applier.py  -- RootConfig reconstruction
    architecture_applier.py -- Role/workflow creation
    prompt_applier.py  -- Constitutional principle injection

  mcp/                 -- MCP signal server (first slice of API-as-MCP)
    server.py          -- Server registration
    tools.py           -- 9 tool definitions

  chief_of_staff/      -- Interactive agent role
    role.py            -- CustomRole definition
    prompts.py         -- Analysis prompt templates
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Meta-analyst | Interactive Chief of Staff agent | Company metaphor, conversational UX, evolvable via #243 |
| Signal access | MCP tools | First slice of API-as-MCP; agents use native tool interface |
| Proposal generation | Rule-first hybrid | Rules detect (cheap, auditable); LLM synthesizes (creative, scoped) |
| Altitudes | Config + Architecture + Prompt | All pluggable, config enabled by default, others opt-in |
| Scope | Deployment-level only | Product-level improvement is a separate future issue |
| Rollout | Before/after default, canary opt-in | Per-proposal choice; configurable observation window |
| Regression | Tiered: threshold + statistical | Layer 1 for catastrophic, Layer 2 for subtle degradation |
| Signals consumed | All 7 domains | Performance, budget, coordination, scaling, errors, evolution, telemetry |
| Evolution boundary | Org-wide default; override + advisory alternatives | Clear separation from per-agent #243 |
| Safe defaults | Disabled, opt-in, mandatory approval | Never auto-applies without human review |

## Signal Domains

| Domain | Source | Key Metrics |
|--------|--------|-------------|
| Performance | `PerformanceTracker` | Quality, success rate, collaboration, trends (all windows) |
| Budget | Budget pure functions | Spend, category breakdown, orchestration ratio, forecast |
| Coordination | Coordination metrics | 9 composable metrics (Ec, O%, Ae, etc.) |
| Scaling | `ScalingService` | Decision outcomes, success rate, signal patterns |
| Errors | Classification pipeline | Category distribution, severity histogram, trends |
| Evolution | `EvolutionService` | Proposal outcomes, approval rate, axis distribution |
| Telemetry | Telemetry pipeline | Event counts, top event types, error events |

## Built-in Rules

| Rule | Severity | Triggers When |
|------|----------|---------------|
| `quality_declining` | WARNING | Org quality below threshold |
| `success_rate_drop` | WARNING | Success rate below threshold |
| `budget_overrun` | CRITICAL | Budget exhaustion imminent |
| `coordination_cost_ratio` | WARNING | Coordination spend too high |
| `coordination_overhead` | WARNING | Coordination overhead % too high |
| `straggler_bottleneck` | INFO | Straggler gap ratio consistently high |
| `redundancy` | INFO | Work redundancy rate too high |
| `scaling_failure` | WARNING | Scaling decisions failing too often |
| `error_spike` | WARNING | Error findings exceed threshold |

All thresholds are configurable via constructor arguments.

## Proposal Lifecycle

1. **Signal collection**: `SnapshotBuilder` runs all 7 aggregators in parallel
2. **Rule evaluation**: `RuleEngine` checks all enabled rules against the snapshot
3. **Strategy dispatch**: Matching strategies generate proposals (rule-first hybrid)
4. **Guard chain**: Sequential evaluation (scope, rollback plan, rate limit, approval gate)
5. **Human approval**: Proposals queue in `ApprovalStore` for mandatory review
6. **Rollout**: Before/after comparison or canary subset (per proposal)
7. **Regression detection**: Tiered (threshold circuit-breaker + statistical significance)
8. **Auto-rollback**: On regression, `RollbackExecutor` applies the rollback plan

## Configuration

```yaml
self_improvement:
  enabled: false                    # Master switch (opt-in)
  chief_of_staff_enabled: false     # Agent persona (opt-in)
  config_tuning_enabled: true       # Config changes (on when enabled)
  architecture_proposals_enabled: false  # Structural changes (opt-in)
  prompt_tuning_enabled: false      # Prompt policies (opt-in)
  schedule:
    cycle_interval_hours: 168       # Weekly
    inflection_trigger_enabled: true
  rollout:
    default_strategy: before_after
    observation_window_hours: 48
    regression_check_interval_hours: 4
  regression:
    quality_drop_threshold: 0.10
    cost_increase_threshold: 0.20
    error_rate_increase_threshold: 0.15
    success_rate_drop_threshold: 0.10
    statistical_significance_level: 0.05
    min_data_points: 10
  guards:
    proposal_rate_limit: 10
    rate_limit_window_hours: 24
```

## Safety Mechanisms

- **Mandatory human approval**: Every proposal goes through `ApprovalStore`. No auto-apply.
- **Guard chain**: 4 sequential guards must all pass before approval routing.
- **Rollback plans**: Every proposal must carry a concrete, validated rollback plan.
- **Tiered regression detection**: Instant circuit-breaker + delayed statistical test.
- **Auto-rollback**: On regression, the rollback plan executes automatically.
- **Rate limiting**: Configurable proposal submission limits prevent flood.
- **Scope enforcement**: Proposals outside enabled altitudes are rejected.
- **Disabled by default**: The entire system is opt-in.

## Follow-up Issues

1. Full API-as-MCP server (extend signal MCP to wrap all API endpoints)
2. Product-level improvement (framework code modification proposals)
3. Cross-deployment analytics (anonymized multi-org patterns)
4. Chief of Staff advanced capabilities (memory-based learning, proactive alerts)
5. Custom rule authoring UI (visual rule builder)
6. A/B testing rollout strategy (parallel config evaluation)
