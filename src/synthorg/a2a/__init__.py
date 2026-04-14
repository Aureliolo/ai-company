"""A2A external gateway -- optional JSON-RPC 2.0 federation layer.

Disabled by default (``A2AConfig.enabled = False``).  When enabled,
exposes SynthOrg agents for federation with external A2A-compatible
systems.  All credential management is routed through the unified
connection catalog, push notifications reuse the generic webhook
receiver, and Agent Cards are computed at request time from
``AgentIdentity`` via a safe-subset projection.
"""
