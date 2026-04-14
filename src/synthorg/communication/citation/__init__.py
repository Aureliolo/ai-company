"""Citation tracking for inter-agent research tasks."""

from synthorg.communication.citation.manager import CitationManager
from synthorg.communication.citation.models import Citation
from synthorg.communication.citation.normalizer import normalize_url

__all__ = [
    "Citation",
    "CitationManager",
    "normalize_url",
]
