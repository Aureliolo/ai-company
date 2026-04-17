"""Communication namespace setting definitions.

Covers bus/NATS transport, event stream, delegation record store,
loop prevention, and bus bridges for API and engine workflow.
"""

from synthorg.observability import get_logger
from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

logger = get_logger(__name__)

_r = get_registry()

# ── Bus bridges (API + workflow webhook) ─────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="bus_bridge_poll_timeout_seconds",
        type=SettingType.FLOAT,
        default="1.0",
        description="Poll timeout for the API bus bridge loop",
        group="Bus Bridge",
        level=SettingLevel.ADVANCED,
        min_value=0.1,
        max_value=10.0,
        yaml_path="communication.bus_bridge.poll_timeout_seconds",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="bus_bridge_max_consecutive_errors",
        type=SettingType.INTEGER,
        default="30",
        description=("Maximum consecutive errors before the API bus bridge aborts"),
        group="Bus Bridge",
        level=SettingLevel.ADVANCED,
        min_value=5,
        max_value=100,
        yaml_path="communication.bus_bridge.max_consecutive_errors",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="webhook_bridge_poll_timeout_seconds",
        type=SettingType.FLOAT,
        default="1.0",
        description="Poll timeout for the engine workflow webhook bridge",
        group="Bus Bridge",
        level=SettingLevel.ADVANCED,
        min_value=0.1,
        max_value=10.0,
        yaml_path="communication.webhook_bridge.poll_timeout_seconds",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="webhook_bridge_max_consecutive_errors",
        type=SettingType.INTEGER,
        default="30",
        description=("Maximum consecutive errors before the webhook bridge aborts"),
        group="Bus Bridge",
        level=SettingLevel.ADVANCED,
        min_value=5,
        max_value=100,
        yaml_path="communication.webhook_bridge.max_consecutive_errors",
    )
)

# ── NATS transport ───────────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="nats_history_batch_size",
        type=SettingType.INTEGER,
        default="100",
        description=("Message batch size for NATS JetStream history replay fetch"),
        group="NATS",
        level=SettingLevel.ADVANCED,
        min_value=10,
        max_value=1000,
        yaml_path="communication.nats.history_batch_size",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="nats_history_fetch_timeout_seconds",
        type=SettingType.FLOAT,
        default="0.5",
        description="Per-batch fetch timeout for NATS history replay",
        group="NATS",
        level=SettingLevel.ADVANCED,
        min_value=0.1,
        max_value=5.0,
        yaml_path="communication.nats.history_fetch_timeout_seconds",
    )
)

# ── Delegation + event stream + loop prevention ──────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="delegation_record_store_max_size",
        type=SettingType.INTEGER,
        default="10000",
        description=(
            "Maximum delegation records retained in the in-memory store before"
            " FIFO eviction. NOTE: DelegationRecordStore is constructed by the"
            " caller of create_app (not inside create_app itself), so this"
            " setting is surfaced for completeness but is not yet threaded into"
            " the default construction path. Wiring is tracked as follow-up on"
            " #1398/#1400; until then a change requires rebuilding the store"
            " with the desired max_records and restarting the process."
        ),
        group="Delegation",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=100,
        max_value=1_000_000,
        yaml_path="communication.delegation.record_store_max_size",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="event_stream_max_queue_size",
        type=SettingType.INTEGER,
        default="256",
        description=(
            "Maximum events buffered per subscriber queue before backpressure"
            " kicks in. NOTE: EventStreamHub is constructed inside create_app"
            " before the ConfigResolver is available, and asyncio.Queue is"
            " created at subscribe time with a fixed maxsize -- changing the"
            " value on an existing hub would only affect new subscribers."
            " Runtime wiring is tracked as follow-up on #1398/#1400; until then"
            " a change requires a process restart with the default overridden"
            " at EventStreamHub construction."
        ),
        group="Event Stream",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=16,
        max_value=10000,
        yaml_path="communication.event_stream.max_queue_size",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMMUNICATION,
        key="loop_prevention_window_seconds",
        type=SettingType.FLOAT,
        default="60.0",
        description=(
            "Window over which repeated inter-agent messages are tracked"
            " for loop detection"
        ),
        group="Loop Prevention",
        level=SettingLevel.ADVANCED,
        min_value=5.0,
        max_value=600.0,
        yaml_path="communication.loop_prevention.window_seconds",
    )
)
