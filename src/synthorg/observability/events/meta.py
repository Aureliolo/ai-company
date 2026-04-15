"""Self-improvement meta-loop event constants for structured logging.

Constants follow the ``meta.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

# -- Cycle events -------------------------------------------------------

META_CYCLE_STARTED: Final[str] = "meta.cycle.started"
META_CYCLE_COMPLETED: Final[str] = "meta.cycle.completed"
META_CYCLE_NO_TRIGGERS: Final[str] = "meta.cycle.no_triggers"
META_CYCLE_FAILED: Final[str] = "meta.cycle.failed"

# -- Signal aggregation events ------------------------------------------

META_SIGNAL_AGGREGATION_STARTED: Final[str] = "meta.signals.aggregation_started"
META_SIGNAL_AGGREGATION_COMPLETED: Final[str] = "meta.signals.aggregation_completed"
META_SIGNAL_AGGREGATION_FAILED: Final[str] = "meta.signals.aggregation_failed"

# -- Rule events --------------------------------------------------------

META_RULE_EVALUATED: Final[str] = "meta.rule.evaluated"
META_RULE_FIRED: Final[str] = "meta.rule.fired"

# -- Proposal events ----------------------------------------------------

META_PROPOSAL_GENERATED: Final[str] = "meta.proposal.generated"
META_PROPOSAL_GUARD_PASSED: Final[str] = "meta.proposal.guard_passed"
META_PROPOSAL_GUARD_REJECTED: Final[str] = "meta.proposal.guard_rejected"
META_PROPOSAL_APPROVED: Final[str] = "meta.proposal.approved"
META_PROPOSAL_REJECTED: Final[str] = "meta.proposal.rejected"

# -- Rollout events -----------------------------------------------------

META_ROLLOUT_PRECONDITION_FAILED: Final[str] = "meta.rollout.precondition_failed"
META_ROLLOUT_STARTED: Final[str] = "meta.rollout.started"
META_ROLLOUT_COMPLETED: Final[str] = "meta.rollout.completed"
META_ROLLOUT_REGRESSION_DETECTED: Final[str] = "meta.rollout.regression_detected"
META_ROLLOUT_FAILED: Final[str] = "meta.rollout.failed"

# -- Regression events --------------------------------------------------

META_REGRESSION_THRESHOLD_BREACH: Final[str] = "meta.regression.threshold_breach"
META_REGRESSION_STATISTICAL: Final[str] = "meta.regression.statistical"

# -- A/B test events ----------------------------------------------------

META_ABTEST_GROUPS_ASSIGNED: Final[str] = "meta.abtest.groups_assigned"
META_ABTEST_OBSERVATION_STARTED: Final[str] = "meta.abtest.observation_started"
META_ABTEST_WINNER_DECLARED: Final[str] = "meta.abtest.winner_declared"
META_ABTEST_INCONCLUSIVE: Final[str] = "meta.abtest.inconclusive"
META_ABTEST_TREATMENT_REGRESSED: Final[str] = "meta.abtest.treatment_regressed"

# -- Rollback events ----------------------------------------------------

META_ROLLBACK_STARTED: Final[str] = "meta.rollback.started"
META_ROLLBACK_COMPLETED: Final[str] = "meta.rollback.completed"
META_ROLLBACK_FAILED: Final[str] = "meta.rollback.failed"

# -- Apply events -------------------------------------------------------

META_APPLY_STARTED: Final[str] = "meta.apply.started"
META_APPLY_COMPLETED: Final[str] = "meta.apply.completed"
META_APPLY_FAILED: Final[str] = "meta.apply.failed"

# -- Rule/factory/config events -----------------------------------------

META_RULE_EVALUATION_FAILED: Final[str] = "meta.rule.evaluation_failed"

META_CONFIG_LOADED: Final[str] = "meta.config.loaded"
META_STRATEGY_REGISTERED: Final[str] = "meta.strategy.registered"

# -- Custom rule CRUD events -----------------------------------------------

META_CUSTOM_RULE_SAVED: Final[str] = "meta.custom_rule.saved"
META_CUSTOM_RULE_SAVE_FAILED: Final[str] = "meta.custom_rule.save_failed"
META_CUSTOM_RULE_FETCHED: Final[str] = "meta.custom_rule.fetched"
META_CUSTOM_RULE_FETCH_FAILED: Final[str] = "meta.custom_rule.fetch_failed"
META_CUSTOM_RULE_LISTED: Final[str] = "meta.custom_rule.listed"
META_CUSTOM_RULE_LIST_FAILED: Final[str] = "meta.custom_rule.list_failed"
META_CUSTOM_RULE_DELETED: Final[str] = "meta.custom_rule.deleted"
META_CUSTOM_RULE_DELETE_FAILED: Final[str] = "meta.custom_rule.delete_failed"
META_CUSTOM_RULE_CREATED: Final[str] = "meta.custom_rule.created"
META_CUSTOM_RULE_UPDATED: Final[str] = "meta.custom_rule.updated"
META_CUSTOM_RULE_TOGGLED: Final[str] = "meta.custom_rule.toggled"
