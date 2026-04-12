"""Engine middleware layer.

Composable middleware protocols for agent execution and multi-agent
coordination pipelines.  Agent middleware hooks into the per-agent
execution loop; coordination middleware hooks into the multi-agent
decompose-route-dispatch-rollup pipeline.

Both protocols follow the project's pluggable subsystem pattern:
``Protocol + Strategy + Factory + Config Discriminator``.
"""
