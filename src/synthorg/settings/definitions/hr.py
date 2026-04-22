"""HR namespace setting definitions (CFG-1 audit).

Covers kill switches and tuning knobs for the HR subsystems:
training pipeline, evaluation metrics, personality composite weights.
"""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

# ── Training pipeline kill switch ────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="training_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description=(
            "Master kill switch for the training pipeline. When False,"
            " training ingestion and curation are paused."
        ),
        group="Training",
        level=SettingLevel.ADVANCED,
        yaml_path="hr.training.enabled",
    )
)

# ── Evaluation metric granular toggles ───────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="evaluation_quality_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Record quality metrics during evaluation",
        group="Evaluation",
        level=SettingLevel.ADVANCED,
        yaml_path="hr.evaluation.quality_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="evaluation_cost_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Record cost metrics during evaluation",
        group="Evaluation",
        level=SettingLevel.ADVANCED,
        yaml_path="hr.evaluation.cost_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="evaluation_latency_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Record latency metrics during evaluation",
        group="Evaluation",
        level=SettingLevel.ADVANCED,
        yaml_path="hr.evaluation.latency_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="evaluation_task_count_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Record task-count metrics during evaluation",
        group="Evaluation",
        level=SettingLevel.ADVANCED,
        yaml_path="hr.evaluation.task_count_enabled",
    )
)

# ── Personality composite weights (visibility) ───────────────────
# Surfaced so operators see the weights in the dashboard. Live-tuning
# requires restart since the weights are read at compute_compatibility()
# call time via module-level constants.

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="personality_big_five_weight",
        type=SettingType.FLOAT,
        default="0.6",
        description=(
            "Weight of the Big Five component in personality"
            " compatibility scoring. Must sum to 1.0 with"
            " personality_collaboration_weight and"
            " personality_conflict_weight."
        ),
        group="Personality Weights",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=0.0,
        max_value=1.0,
        yaml_path="hr.personality_big_five_weight",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="personality_collaboration_weight",
        type=SettingType.FLOAT,
        default="0.2",
        description=(
            "Weight of the collaboration-preference component in"
            " personality compatibility scoring."
        ),
        group="Personality Weights",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=0.0,
        max_value=1.0,
        yaml_path="hr.personality_collaboration_weight",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.HR,
        key="personality_conflict_weight",
        type=SettingType.FLOAT,
        default="0.2",
        description=(
            "Weight of the conflict-approach component in personality"
            " compatibility scoring."
        ),
        group="Personality Weights",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=0.0,
        max_value=1.0,
        yaml_path="hr.personality_conflict_weight",
    )
)
