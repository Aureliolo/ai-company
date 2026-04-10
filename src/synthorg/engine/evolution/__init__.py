"""Agent evolution and improvement system.

Provides the pluggable evolution pipeline: triggers detect when
evolution should run, proposers generate adaptation proposals,
guards validate proposals, and adapters apply approved changes
to agent identity, strategy selection, or prompt templates.
"""
