"""Infrastructure MCP facades.

Thin per-subdomain facades used by the ``synthorg_settings_*``,
``synthorg_providers_*``, ``synthorg_backup_*``, etc. MCP tools.  Each
facade wraps a primitive that is already attached to :class:`AppState`
and raises :class:`~synthorg.communication.mcp_errors.CapabilityNotSupportedError`
for operations the primitive does not yet implement.
"""
