"""Fine-tune pipeline container entrypoint.

Reads stage configuration from ``/etc/fine-tune/config.json``, executes
the requested pipeline stage, and emits structured progress markers on
stdout for the orchestrator to parse.

Designed to run as ``python -m synthorg.memory.embedding.fine_tune_runner``
inside the ``synthorg-fine-tune`` container.

Uses ``print()`` for structured stdout/stderr markers that the
orchestrator parses from Docker container logs -- this is an entrypoint
script, not application library code.
"""

import json
import signal
import sys
from pathlib import Path

from synthorg.memory.embedding.cancellation import CancellationToken
from synthorg.memory.embedding.fine_tune import (
    FineTuneStage,
    contrastive_fine_tune,
    deploy_checkpoint,
    evaluate_checkpoint,
    generate_training_data,
    mine_hard_negatives,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = Path("/etc/fine-tune/config.json")

_STAGE_FUNCTIONS = {
    FineTuneStage.GENERATING_DATA: generate_training_data,
    FineTuneStage.MINING_NEGATIVES: mine_hard_negatives,
    FineTuneStage.TRAINING: contrastive_fine_tune,
    FineTuneStage.EVALUATING: evaluate_checkpoint,
    FineTuneStage.DEPLOYING: deploy_checkpoint,
}


def _run() -> int:
    """Execute the fine-tune stage and return an exit code."""
    if not _CONFIG_PATH.exists():
        print(  # noqa: T201
            f"ERROR: config file not found at {_CONFIG_PATH}",
            file=sys.stderr,
        )
        return 1

    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    stage_name = config.get("stage", "")

    try:
        stage = FineTuneStage(stage_name)
    except ValueError:
        print(f"ERROR: unknown stage {stage_name!r}", file=sys.stderr)  # noqa: T201
        return 1

    stage_fn = _STAGE_FUNCTIONS.get(stage)
    if stage_fn is None:
        print(f"ERROR: stage {stage_name!r} is not executable", file=sys.stderr)  # noqa: T201
        return 1

    # Cooperative cancellation via SIGTERM (docker stop).
    token = CancellationToken()
    signal.signal(signal.SIGTERM, lambda *_: token.cancel())

    print(f"STAGE_START:{stage_name}", flush=True)  # noqa: T201
    try:
        stage_fn(config=config, cancellation=token)
    except Exception as exc:
        print(f"ERROR: {stage_name} failed: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(f"STAGE_COMPLETE:{stage_name}", flush=True)  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(_run())
