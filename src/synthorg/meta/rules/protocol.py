"""Protocol for signal rules.

Re-exports the SignalRule protocol from the meta protocol module
for convenience. Rules are deterministic pattern detectors that
fire when specific signal conditions are met.
"""

from synthorg.meta.protocol import SignalRule

__all__ = ["SignalRule"]
