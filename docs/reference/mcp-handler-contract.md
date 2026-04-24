# MCP Handler Contract

On-demand reference for implementing tool handlers in `src/synthorg/meta/mcp/handlers/<domain>.py`. The overview / invariants live in `CLAUDE.md` under "MCP Handler Layer". See also `docs/design/tools.md` §"SynthOrg MCP Tool Surface" for the user-facing contract and `docs/design/observability.md` §"MCP handler events" for the event inventory.

## Surface

SynthOrg exposes 204 tools across 15 domains via its MCP server. Tools are classified by capability action (`read_tool` / `write_tool` / `admin_tool`) via the builders in `src/synthorg/meta/mcp/tool_builder.py`; only the `admin_tool` subset is destructive and subject to the guardrail triple.

## ToolHandler protocol

**Signature**: `async def _<tool>(*, app_state, arguments, actor: AgentIdentity | None = None) -> str`. The `actor` kwarg threads calling-agent identity through the invoker so destructive-op guardrails can attribute audit records. Handlers that don't care about identity still accept and ignore it.

## Envelope

Return a JSON string built by helpers in `src/synthorg/meta/mcp/handlers/common.py`:



- `ok(data, pagination=...)` for success.
- `err(exc)` for caught errors. Envelope picks up `domain_code="invalid_argument"` automatically on `ArgumentValidationError` / `GuardrailViolationError`. Set custom codes via `err(exc, domain_code="...")`.
- `capability_gap(tool, reason)` when the handler is wired but the underlying primitive does not expose the required method. Emits `MCP_HANDLER_CAPABILITY_GAP` at INFO.
- `not_supported(tool, reason)` for tools registered without a concrete handler. Emits `MCP_HANDLER_NOT_IMPLEMENTED` at WARNING.

Never emit a bare `{"status": "not_implemented"}` payload; `make_placeholder_handler` delegates to `not_supported()` so every unwired tool ships the single agreed envelope. The legacy `service_fallback()` helper is retained in `common.py` but has zero call sites after META-MCP-2; `tests/integration/mcp/test_tool_surface.py` asserts zero `MCP_HANDLER_SERVICE_FALLBACK` emissions across the full 204-tool surface.

## Argument validation

Use `require_arg(arguments, key, ty)` for typed required extraction; catch `ArgumentValidationError` and return `err(exc)`. Never let raw `TypeError` / `ValueError` escape from `int(...)` / enum coercion; wrap them and call `invalid_argument(name, expected)`.

## Destructive ops

Call `require_destructive_guardrails(arguments, actor)` first. It enforces:

- non-`None` `actor`
- literal `confirm=True`
- non-blank `reason`

and raises `GuardrailViolationError` with a typed `violation: Literal["missing_actor", "missing_confirm", "missing_reason"]`. Emit `MCP_DESTRUCTIVE_OP_EXECUTED` exactly once per successful destructive call for the audit trail. Schema-level reject whitespace reasons with `"minLength": 1, "pattern": r".*\S.*"`.

## Registries

Export `XXX_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType({...})` so the registry is read-only. `build_handler_map()` aggregates across domains and raises on duplicate keys.

## Domain codes

Standard wire codes: `invalid_argument`, `guardrail_violated`, `not_supported`, `not_found`, `conflict`.

## Persistence boundary still applies

Handlers route through service-layer facades (`MemoryService`, `ArtifactService`, etc.), never into `app_state.persistence.*` directly. Reads that need the total count alongside a page should make the service return `(items, total)`.
