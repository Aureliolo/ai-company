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

import asyncio
import json
import signal
import sys
from pathlib import Path
from typing import Any

from synthorg.memory.embedding.cancellation import CancellationToken
from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.observability import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = Path("/etc/fine-tune/config.json")

# Stage functions have different signatures; the runner dispatches by
# unpacking config JSON into kwargs per stage.  Typed as Any because
# mypy cannot narrow across the heterogeneous union.
_EXECUTABLE_STAGES: frozenset[FineTuneStage] = frozenset(
    {
        FineTuneStage.GENERATING_DATA,
        FineTuneStage.MINING_NEGATIVES,
        FineTuneStage.TRAINING,
        FineTuneStage.EVALUATING,
        FineTuneStage.DEPLOYING,
    }
)


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

    if stage not in _EXECUTABLE_STAGES:
        print(f"ERROR: stage {stage_name!r} is not executable", file=sys.stderr)  # noqa: T201
        return 1

    # Cooperative cancellation via SIGTERM (docker stop).
    token = CancellationToken()
    signal.signal(signal.SIGTERM, lambda *_: token.cancel())

    print(f"STAGE_START:{stage_name}", flush=True)  # noqa: T201
    try:
        asyncio.run(_dispatch_stage(stage, config, token))
    except Exception as exc:
        print(f"ERROR: {stage_name} failed: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(f"STAGE_COMPLETE:{stage_name}", flush=True)  # noqa: T201
    return 0


async def _dispatch_stage(
    stage: FineTuneStage,
    config: dict[str, Any],
    token: CancellationToken,
) -> None:
    """Dispatch a stage call with the correct kwargs from config JSON."""
    # Lazy imports -- only load ML deps when actually running a stage.
    from synthorg.memory.embedding.fine_tune import (  # noqa: PLC0415
        contrastive_fine_tune,
        deploy_checkpoint,
        evaluate_checkpoint,
        generate_training_data,
        mine_hard_negatives,
    )

    match stage:
        case FineTuneStage.GENERATING_DATA:
            await generate_training_data(
                source_dir=config["source_dir"],
                output_dir=config["output_dir"],
                cancellation=token,
            )
        case FineTuneStage.MINING_NEGATIVES:
            await mine_hard_negatives(
                training_data_path=config["training_data_path"],
                base_model=config["base_model"],
                output_dir=config["output_dir"],
                cancellation=token,
            )
        case FineTuneStage.TRAINING:
            await contrastive_fine_tune(
                training_data_path=config["training_data_path"],
                base_model=config["base_model"],
                output_dir=config["output_dir"],
                cancellation=token,
            )
        case FineTuneStage.EVALUATING:
            await evaluate_checkpoint(
                checkpoint_path=config["checkpoint_path"],
                base_model=config["base_model"],
                validation_data_path=config["validation_data_path"],
                output_dir=config["output_dir"],
                cancellation=token,
            )
        case FineTuneStage.DEPLOYING:
            await deploy_checkpoint(
                checkpoint_path=config["checkpoint_path"],
            )


if __name__ == "__main__":
    sys.exit(_run())
