"""Re-export Evidence Package models from core.

The canonical definitions live in ``synthorg.core.evidence`` to avoid
circular imports (``core.approval`` -> ``communication`` -> ``core``).
This module re-exports them so callers within the ``communication``
package can use the shorter import path.
"""

from synthorg.core.evidence import EvidencePackage, RecommendedAction

__all__ = ["EvidencePackage", "RecommendedAction"]
