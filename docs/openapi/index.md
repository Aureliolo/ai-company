# REST API Reference

SynthOrg exposes a REST + WebSocket API built on [Litestar](https://litestar.dev/). The API is the primary integration surface for the web dashboard, the Go CLI, and any external clients that want to drive a synthetic organization programmatically.

**[Open Interactive Reference :material-open-in-new:](reference.html){ .md-button .md-button--primary }**
**[Download OpenAPI Schema :material-download:](openapi.json){ .md-button }**

---

## Base URL and Versioning

All endpoints live under a version-prefixed path:

```
https://<your-host>/api/v1
```

The prefix is configurable via the `api_prefix` field of `ApiConfig` (default `/api/v1`). Breaking changes bump the path version; additive changes (new fields, new endpoints, relaxed constraints) ship under the existing version.

When running the server locally you also get two kinds of side paths -- documentation paths (mounted by Litestar at a **fixed** prefix independent of `api_prefix`) and API paths (relative to `api_prefix`):

**Documentation paths (fixed at `/docs/*`):**

| Path | Content |
|---|---|
| `/docs/api` | Scalar UI live against your running server |
| `/docs/openapi.json` | Live OpenAPI schema for the running server |

**API paths (move with `api_prefix`, shown with the default `/api/v1`):**

| Path | Content |
|---|---|
| `/api/v1/health` | Liveness + readiness endpoint |
| `/api/v1/ws` | WebSocket endpoint for server-sent events (approvals, meetings, task lifecycle) |

The static snapshot on this page is produced by `scripts/export_openapi.py`, which takes the live Litestar schema and runs it through `inject_rfc9457_responses` to attach RFC 9457 error response shapes to every operation. The result is a superset of what `/docs/openapi.json` returns at runtime.

---

## Authentication

SynthOrg uses **JWT session tokens** issued by the auth controller. The typical flow:

1. **First-run setup.** On a fresh install, `POST /api/v1/auth/setup` creates the initial CEO account. After setup completes, this endpoint returns a conflict error.
2. **Login.** `POST /api/v1/auth/login` with a username and password returns a signed JWT plus a session record. Include the token on subsequent requests as `Authorization: Bearer <token>`.
3. **Password change.** New users are forced through `POST /api/v1/auth/change-password` before any other endpoint accepts their token -- the `require_password_changed` guard blocks everything else until the temporary password is rotated.
4. **Current identity.** `GET /api/v1/auth/me` returns the authenticated user, role, and session metadata.
5. **WebSocket tickets.** Browsers can't set `Authorization` headers on WebSocket connections, so `POST /api/v1/auth/ws-ticket` mints a short-lived single-use ticket. The **preferred** way to present it is as the first WebSocket message (`{"action": "auth", "ticket": "<ticket>"}`) so the ticket never lands in URLs, access logs, or browser history. A legacy `/api/v1/ws?ticket=<ticket>` query-param form is also accepted and is validated before the WebSocket upgrade.
6. **Session management.** `GET /api/v1/auth/sessions` lists the caller's active sessions. `DELETE /api/v1/auth/sessions/{session_id}` revokes a specific session. `POST /api/v1/auth/logout` revokes the session backing the current token (the normal "log out of this browser" action). There is no bulk "revoke all" endpoint.

Passwords are hashed with Argon2id. The server performs a constant-time dummy verification on unknown usernames to prevent timing-based user enumeration.

---

## Endpoint Groups

The API is organised into resource controllers. Every controller is mounted under the `/api/v1` prefix.

### Identity and users

| Resource | Path | Purpose |
|---|---|---|
| Auth | `/auth` | Setup, login, password, sessions, WebSocket tickets |
| Users | `/users` | Human user CRUD (CEO-only), role assignment |

### Organization and agents

| Resource | Path | Purpose |
|---|---|---|
| Company | `/company` | Top-level company identity and config |
| Departments | `/departments` | Department CRUD, membership, policy overrides |
| Agents | `/agents` | Agent CRUD, hiring/firing, personality assignment |
| Agent Autonomy | `/agents/{id}/autonomy` | Per-agent autonomy level and trust policy |
| Agent Collaboration | `/agents/{id}/collaboration` | Peer collaboration rules |
| Agent Quality | `/agents/{id}/quality` | Quality score overrides (L3 human layer) |
| Activities | `/activities` | Activity timeline (lifecycle events, cost events, promotions) |
| Personalities | `/personalities` | Personality preset CRUD |

### Work and coordination

| Resource | Path | Purpose |
|---|---|---|
| Projects | `/projects` | Project CRUD, status, artifacts |
| Tasks | `/tasks` | Task CRUD, assignment, lifecycle transitions |
| Task Coordination | `/tasks/{id}/coordinate` | Multi-agent coordination actions |
| Messages | `/messages` | Inter-agent message bus access |
| Meetings | `/meetings` | Meeting scheduling, participation, minutes |
| Approvals | `/approvals` | Approval gate queue and decisions |
| Artifacts | `/artifacts` | Artifact content storage and retrieval |

### Workflows

| Resource | Path | Purpose |
|---|---|---|
| Workflows | `/workflows` | Visual workflow definition CRUD, validation, YAML export |
| Workflow Versions | `/workflows/{id}/versions` | Version history, diff, rollback |
| Workflow Executions | `/workflow-executions` | Activate, list, get, cancel executions |
| Template Packs | `/template-packs` | Additive team pack listing and live application |
| Setup | `/setup` | First-run wizard endpoints (template selection, personality seeding) |

### Operations and platform

| Resource | Path | Purpose |
|---|---|---|
| Health | `/health` | Liveness + readiness |
| Providers | `/providers` | LLM provider runtime CRUD, model auto-discovery, health |
| Budget | `/budget` | Cost tracking, spend reports, budget enforcement, risk budget |
| Analytics | `/analytics` | Aggregated metrics across agents, tasks, and providers |
| Reports | `/reports` | On-demand and scheduled report generation |
| Memory Admin | `/admin/memory` | Fine-tuning pipeline, checkpoint management, embedder queries |
| Backups | `/admin/backups` | Backup orchestration, scheduling, retention |
| Settings | `/settings` | Runtime-editable settings (DB > env > YAML > code) |
| Ceremony Policy | `/ceremony-policy` | Project and per-department ceremony policy resolution |

Full request/response schemas for every endpoint are in the **[interactive reference](reference.html)**.

---

## Request Patterns

### Pagination

List endpoints accept `limit` and `offset` query parameters and return a `PaginatedResponse[T]` envelope:

```json
{
  "data": [...],
  "pagination": {"total": 142, "offset": 0, "limit": 50},
  "degraded_sources": [],
  "error": null,
  "error_detail": null,
  "success": true
}
```

`data` holds the page of items. `pagination` carries the offset/limit/total triple. `degraded_sources` is empty on a normal response and lists data sources that failed gracefully when the endpoint returned partial data. `error` and `error_detail` are `null` on success; `success` is derived from `error`.

### Optimistic concurrency

The following resources return an `ETag` header on reads: workflow definitions, workflow versions, workflow executions, tasks, and runtime-editable settings. To update them without trampling a concurrent write, pass the ETag back via `If-Match`. A mismatch produces a `409 Conflict` with error code `VERSION_CONFLICT` (4002).

### WebSocket events

Real-time updates (approval requests, meeting state, task transitions, routing decisions) are pushed over `/api/v1/ws`. After authenticating with a ws-ticket, clients send JSON messages to subscribe or unsubscribe from named channels (with optional payload filters), and the server pushes `WsEvent` JSON payloads on subscribed channels. Event types are tagged via a `type` field on each payload.

---

## Error Format

Errors use [RFC 9457 Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc9457):

```json
{
  "type": "https://synthorg.io/docs/errors/#validation-error",
  "title": "Validation failed",
  "status": 422,
  "detail": "Field 'name' is required",
  "code": 2001,
  "category": "validation",
  "instance": "/api/v1/agents"
}
```

The `code` field is a 4-digit machine-readable error code grouped by category:

| Range | Category | Examples |
|---|---|---|
| 1xxx | `auth` | `UNAUTHORIZED`, `FORBIDDEN`, `SESSION_REVOKED` |
| 2xxx | `validation` | `VALIDATION_ERROR`, `REQUEST_VALIDATION_ERROR` |
| 3xxx | `not_found` | `RESOURCE_NOT_FOUND`, `RECORD_NOT_FOUND`, `ROUTE_NOT_FOUND` |
| 4xxx | `conflict` | `RESOURCE_CONFLICT`, `DUPLICATE_RECORD`, `VERSION_CONFLICT` |
| 5xxx | `rate_limit` | `RATE_LIMITED` |
| 6xxx | `budget_exhausted` | `BUDGET_EXHAUSTED` |
| 7xxx | `provider_error` | Upstream LLM provider failures |
| 8xxx | `internal` | Unhandled server errors |

The full error taxonomy lives in the [Error Reference](../errors.md).

---

## Rate Limiting

The API applies per-IP rate limiting via Litestar's built-in `RateLimitConfig`. Limits are configurable per deployment. Clients that exceed the limit receive `429 Too Many Requests` with code `RATE_LIMITED` (5000) and a `Retry-After` header.

---

## CORS

CORS is disabled by default for non-local origins. Add trusted dashboard origins via `ApiConfig.cors.allowed_origins`. Wildcard origins (`*`) cannot be combined with `allow_credentials=true`.

---

## Further Reading

- **[Interactive API Reference](reference.html)** -- every endpoint, request body, and response schema
- **[OpenAPI Schema](openapi.json)** -- raw schema for codegen and tooling
- **[Error Reference](../errors.md)** -- full error taxonomy and codes
- **[Security](../security.md)** -- authn/authz design, trust levels, audit log
- **[Architecture](../architecture/index.md)** -- where the API sits in the overall system
