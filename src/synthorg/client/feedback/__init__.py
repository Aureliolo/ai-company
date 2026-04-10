"""Feedback strategy implementations for client simulation."""

from synthorg.client.feedback.adversarial import AdversarialFeedback
from synthorg.client.feedback.binary import BinaryFeedback
from synthorg.client.feedback.criteria_check import CriteriaCheckFeedback
from synthorg.client.feedback.scored import ScoredFeedback

__all__ = [
    "AdversarialFeedback",
    "BinaryFeedback",
    "CriteriaCheckFeedback",
    "ScoredFeedback",
]
