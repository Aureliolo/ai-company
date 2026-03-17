"""Context compaction subpackage.

Provides a pluggable compaction hook for execution loops that
compresses older conversation turns when the context window
fill level exceeds a configurable threshold.
"""

from synthorg.engine.compaction.models import (
    CompactionConfig,
    CompressionMetadata,
)
from synthorg.engine.compaction.protocol import CompactionCallback

__all__ = [
    "CompactionCallback",
    "CompactionConfig",
    "CompressionMetadata",
]
