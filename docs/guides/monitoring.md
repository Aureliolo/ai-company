---
title: Monitoring & Dashboards
description: Prometheus metric inventory, suggested PromQL queries, Grafana dashboard import, and Logfire integration notes.
---

# Monitoring & Dashboards

SynthOrg exposes runtime telemetry via a Prometheus `/metrics` endpoint plus structured JSON logs. This guide walks through the metric surface, a ready-to-import Grafana dashboard, and suggested alert rules. For the raw metric implementation, see `src/synthorg/observability/prometheus_collector.py`.

## Scraping

Point any Prometheus-compatible scraper at the running app:

```yaml
scrape_configs:
  - job_name: synthorg
    scrape_interval: 30s
    static_configs:
      - targets: ['synthorg:8000']
```

The endpoint is unauthenticated by default; put it behind your normal scrape-ACL (firewall, sidecar proxy, Kubernetes NetworkPolicy). All metric names are prefixed with `synthorg_`.

## Metric inventory

### Coordination (push-updated per multi-agent run)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `synthorg_coordination_efficiency` | Gauge | -- | 0.0-1.0 efficiency ratio |
| `synthorg_coordination_overhead_percent` | Gauge | -- | % of wall time spent coordinating |

### Cost & budget (pull-refreshed at scrape)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `synthorg_cost_total` | Gauge | -- | Total accumulated cost |
| `synthorg_budget_used_percent` | Gauge | -- | Monthly budget utilisation |
| `synthorg_budget_monthly_cost` | Gauge | -- | Monthly budget in configured currency |
| `synthorg_budget_daily_used_percent` | Gauge | -- | Daily utilisation (prorated) |
| `synthorg_agent_cost_total` | Gauge | `agent_id` | Per-agent accumulated cost |
| `synthorg_agent_budget_used_percent` | Gauge | `agent_id` | Per-agent daily utilisation |

### Agents & tasks

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `synthorg_active_agents_total` | Gauge | `status`, `trust_level` | Active agent count by status |
| `synthorg_tasks_total` | Gauge | `status`, `agent` | Task count per status per agent |

### Providers & tools

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `synthorg_provider_tokens_total` | Counter | `provider`, `model`, `direction` | Input/output tokens by model |
| `synthorg_provider_cost_total` | Counter | `provider`, `model` | Cost per provider call |
| `synthorg_api_requests_total` | Counter | `method`, `route`, `status_class` | API request rate |
| `synthorg_tool_invocations_total` | Counter | `tool_name`, `outcome` | Tool invocations by outcome |

### HYG-1 additions

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `synthorg_escalation_queue_depth` | Gauge | `department` | Pending escalations awaiting decision |
| `synthorg_agent_identity_version_changes_total` | Counter | `agent_id`, `change_type` | Identity-version lifecycle events. ``change_type`` is bounded to ``created`` / ``updated`` / ``rolled_back`` / ``archived`` by the collector (``VALID_IDENTITY_CHANGE_TYPES``). |
| `synthorg_workflow_execution_seconds` | Histogram | `workflow_definition_id`, `status` | Workflow execution duration (``workflow_definition_id`` is the stable definition id, bounded). ``status`` is bounded to ``completed`` / ``failed`` / ``cancelled`` / ``timeout`` by the collector (``VALID_WORKFLOW_EXECUTION_STATUSES``). |

Bounded-label values are enforced at record time in `src/synthorg/observability/prometheus_labels.py` -- PromQL filters that reference values outside the lists above will never match data.

## Suggested PromQL queries

### Saturation / backlog

```promql
# Escalation backlog (any department) sustained above 5 for 10m
max_over_time(synthorg_escalation_queue_depth[10m]) > 5

# Workflow p95 latency exceeds 60s
histogram_quantile(0.95, sum by (le) (rate(synthorg_workflow_execution_seconds_bucket[5m]))) > 60
```

### Cost / budget

```promql
# Burned 80% of the monthly budget
synthorg_budget_used_percent > 80

# Per-agent cost top 5 (most expensive right now)
topk(5, synthorg_agent_cost_total)
```

### Coordination health

```promql
# Coordination overhead sustained above 40% for 10 minutes
avg_over_time(synthorg_coordination_overhead_percent[10m]) > 40

# Coordination efficiency dropped below 0.5 (half of runs wasted)
avg_over_time(synthorg_coordination_efficiency[15m]) < 0.5
```

### Identity lifecycle

```promql
# Rollback rate over the last hour (audit-relevant spike check)
sum(rate(synthorg_agent_identity_version_changes_total{change_type="rolled_back"}[1h]))

# Churn rate -- identity updates per minute
sum by (change_type) (rate(synthorg_agent_identity_version_changes_total[5m]))
```

### API health

```promql
# 5xx rate as a fraction of total
sum(rate(synthorg_api_requests_total{status_class="5xx"}[5m]))
  / sum(rate(synthorg_api_requests_total[5m]))

# Request rate by status class
sum by (status_class) (rate(synthorg_api_requests_total[1m]))
```

## Grafana dashboard

Import `monitoring/grafana/synthorg-overview.json` into any Grafana v10+ instance. The file is Grafana v10-compatible dashboard JSON (authored against the v11 editor, which emits a backward-compatible schema) with a single `${DS_PROMETHEUS}` template variable bound to your Prometheus data source.

Panels included:

1. Coordination efficiency (gauge, 0.0-1.0)
2. Coordination overhead % (gauge, alert at 40%)
3. Budget utilisation (gauge, alert at 80%)
4. Escalation queue depth (stat, per department)
5. Agent identity changes (timeseries, by `change_type`)
6. Workflow execution p95 (timeseries, by status)
7. Per-agent cost (table, top 25)
8. API request rate (timeseries, by status class)

To install via the Grafana UI: `Dashboards → New → Import → Upload JSON file`. Via the provisioning API: `POST /api/dashboards/db` with `{"dashboard": <file>, "overwrite": true, "inputs": [...]}`.

## Alerts

The file does not ship alert rules because thresholds are deployment-specific. The suggested PromQL above is ready to drop into Prometheus' `rules.yml` -- pair each query with a `labels: severity: warning|critical` and a `for:` duration. Example:

```yaml
groups:
  - name: synthorg
    rules:
      - alert: SynthorgCoordinationOverheadHigh
        expr: avg_over_time(synthorg_coordination_overhead_percent[10m]) > 40
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: "Coordination overhead is {{ $value }}%"
          runbook: "https://synthorg.io/docs/runbooks/coordination-overhead"
```

## Logfire

Logfire's Prometheus integration can scrape the same `/metrics` endpoint directly -- no additional wiring is required on the SynthOrg side. Follow the [Logfire Prometheus setup](https://logfire.pydantic.dev/docs/integrations/metrics/prometheus/) and point it at `http://synthorg:8000/metrics`. All metrics documented above will appear under the same names in Logfire dashboards.

## Further reading

- [Observability design](../design/observability.md) -- sink layout, correlation IDs, per-domain routing
- [Reference: errors](../reference/errors.md) -- RFC 9457 error categories
- `src/synthorg/observability/prometheus_collector.py` -- canonical metric registration
- `src/synthorg/observability/prometheus_labels.py` -- bounded label value sets
