"""Async task service -- supervisor-facing interface over TaskEngine.

Provides five steering operations (start, check, update, cancel, list)
that wrap the existing ``TaskEngine`` single-writer actor. Does NOT
create a parallel task system.
"""

from datetime import UTC, datetime

from synthorg.communication.async_tasks.models import (
    AsyncTaskStatus,
    TaskSpec,
)
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.enums import MessagePriority, MessageType
from synthorg.communication.message import Message, TextPart
from synthorg.core.enums import TaskStatus, TaskType
from synthorg.engine.task_engine import TaskEngine  # noqa: TC001
from synthorg.engine.task_engine_models import CreateTaskData
from synthorg.observability import get_logger
from synthorg.observability.events.async_task import (
    ASYNC_TASK_CANCELLED,
    ASYNC_TASK_CHECKED,
    ASYNC_TASK_LISTED,
    ASYNC_TASK_START_FAILED,
    ASYNC_TASK_STARTED,
    ASYNC_TASK_UPDATED,
)

logger = get_logger(__name__)

# Map internal TaskStatus to supervisor-facing AsyncTaskStatus.
_STATUS_MAP: dict[TaskStatus, AsyncTaskStatus] = {
    TaskStatus.CREATED: AsyncTaskStatus.PENDING,
    TaskStatus.ASSIGNED: AsyncTaskStatus.PENDING,
    TaskStatus.IN_PROGRESS: AsyncTaskStatus.RUNNING,
    TaskStatus.IN_REVIEW: AsyncTaskStatus.RUNNING,
    TaskStatus.BLOCKED: AsyncTaskStatus.RUNNING,
    TaskStatus.AUTH_REQUIRED: AsyncTaskStatus.PENDING,
    TaskStatus.COMPLETED: AsyncTaskStatus.COMPLETED,
    TaskStatus.FAILED: AsyncTaskStatus.FAILED,
    TaskStatus.CANCELLED: AsyncTaskStatus.CANCELLED,
    TaskStatus.REJECTED: AsyncTaskStatus.FAILED,
    TaskStatus.INTERRUPTED: AsyncTaskStatus.FAILED,
    TaskStatus.SUSPENDED: AsyncTaskStatus.PENDING,
}


class AsyncTaskService:
    """Thin supervisor-facing interface over TaskEngine.

    All five operations delegate to the existing ``TaskEngine``
    single-writer actor. No parallel task system is created.

    Args:
        task_engine: The existing task engine instance.
        message_bus: Message bus for context injection messages.
    """

    __slots__ = ("_bus", "_engine")

    def __init__(
        self,
        *,
        task_engine: TaskEngine,
        message_bus: MessageBus,
    ) -> None:
        self._engine = task_engine
        self._bus = message_bus

    async def start_async_task(
        self,
        supervisor_id: str,
        task_spec: TaskSpec,
    ) -> str:
        """Create and assign a task via TaskEngine, return task ID.

        Args:
            supervisor_id: ID of the supervisor starting the task.
            task_spec: Specification of what the subagent should do.

        Returns:
            The created task's ID.
        """
        data = CreateTaskData(
            title=task_spec.title,
            description=task_spec.description,
            type=TaskType.RESEARCH,
            project="default",
            created_by=supervisor_id,
            assigned_to=task_spec.agent_id,
        )
        try:
            task = await self._engine.create_task(
                data,
                requested_by=supervisor_id,
            )
            await self._engine.transition_task(
                task.id,
                TaskStatus.ASSIGNED,
                requested_by=supervisor_id,
                reason="async_task_start",
            )
        except Exception:
            logger.exception(
                ASYNC_TASK_START_FAILED,
                supervisor_id=supervisor_id,
                title=task_spec.title,
            )
            raise

        logger.info(
            ASYNC_TASK_STARTED,
            task_id=task.id,
            agent_id=task_spec.agent_id,
            supervisor_id=supervisor_id,
        )
        return task.id

    async def check_async_task(self, task_id: str) -> AsyncTaskStatus:
        """Project TaskEngine state to AsyncTaskStatus.

        Args:
            task_id: Task identifier to check.

        Returns:
            Current status from the supervisor's perspective.

        Raises:
            LookupError: If the task is not found.
        """
        task = await self._engine.get_task(task_id)
        if task is None:
            msg = f"Async task {task_id} not found"
            raise LookupError(msg)

        status = _STATUS_MAP.get(task.status, AsyncTaskStatus.PENDING)
        logger.debug(
            ASYNC_TASK_CHECKED,
            task_id=task_id,
            status=status.value,
        )
        return status

    async def update_async_task(
        self,
        task_id: str,
        instructions: str,
    ) -> AsyncTaskStatus:
        """Send new instructions to a running task via MessageBus.

        Posts a ``CONTEXT_INJECTION`` message to the executing agent.

        Args:
            task_id: Task to update.
            instructions: New instructions for the executing agent.

        Returns:
            Current status of the task.

        Raises:
            LookupError: If the task is not found.
        """
        task = await self._engine.get_task(task_id)
        if task is None:
            msg = f"Async task {task_id} not found"
            raise LookupError(msg)

        recipient = task.assigned_to or task.created_by
        message = Message(
            timestamp=datetime.now(UTC),
            sender="async_task_service",
            to=recipient,
            type=MessageType.CONTEXT_INJECTION,
            priority=MessagePriority.NORMAL,
            channel=f"@async_task:{task_id}",
            parts=(TextPart(text=instructions),),
        )
        await self._bus.send_direct(message, recipient=recipient)

        status = _STATUS_MAP.get(task.status, AsyncTaskStatus.PENDING)
        logger.info(
            ASYNC_TASK_UPDATED,
            task_id=task_id,
            recipient=recipient,
        )
        return status

    async def cancel_async_task(
        self,
        task_id: str,
        supervisor_id: str,
    ) -> AsyncTaskStatus:
        """Cancel a task via TaskEngine.

        Args:
            task_id: Task to cancel.
            supervisor_id: ID of the supervisor requesting cancellation.

        Returns:
            Updated status (should be CANCELLED).
        """
        task = await self._engine.cancel_task(
            task_id,
            requested_by=supervisor_id,
            reason="ASYNC_CANCEL",
        )
        status = _STATUS_MAP.get(task.status, AsyncTaskStatus.CANCELLED)
        logger.info(
            ASYNC_TASK_CANCELLED,
            task_id=task_id,
            supervisor_id=supervisor_id,
        )
        return status

    async def list_async_tasks(
        self,
        supervisor_task_id: str,
    ) -> tuple[AsyncTaskStatus, ...]:
        """List statuses of tasks under a supervisor task.

        Filters TaskEngine tasks by ``parent_task_id``.

        Args:
            supervisor_task_id: The supervisor's own task ID.

        Returns:
            Tuple of statuses for all child tasks.
        """
        # TaskEngine.list_tasks doesn't filter by parent_task_id
        # directly, so we fetch and filter in-memory.
        tasks, _count = await self._engine.list_tasks()
        child_statuses = tuple(
            _STATUS_MAP.get(t.status, AsyncTaskStatus.PENDING)
            for t in tasks
            if t.parent_task_id == supervisor_task_id
        )
        logger.debug(
            ASYNC_TASK_LISTED,
            supervisor_task_id=supervisor_task_id,
            count=len(child_statuses),
        )
        return child_statuses
