"""Ontology injection strategies for agent context.

Provides the ``OntologyInjectionStrategy`` protocol and four
concrete implementations that control *how* entity definitions
reach agents during execution.
"""

from synthorg.ontology.injection.factory import create_injection_strategy
from synthorg.ontology.injection.hybrid import HybridInjectionStrategy
from synthorg.ontology.injection.memory import MemoryBasedInjectionStrategy
from synthorg.ontology.injection.prompt import PromptInjectionStrategy
from synthorg.ontology.injection.protocol import OntologyInjectionStrategy
from synthorg.ontology.injection.tool import (
    LookupEntityTool,
    ToolBasedInjectionStrategy,
)

__all__ = [
    "HybridInjectionStrategy",
    "LookupEntityTool",
    "MemoryBasedInjectionStrategy",
    "OntologyInjectionStrategy",
    "PromptInjectionStrategy",
    "ToolBasedInjectionStrategy",
    "create_injection_strategy",
]
