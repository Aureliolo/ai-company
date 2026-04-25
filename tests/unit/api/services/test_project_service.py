"""Unit tests for :class:`ProjectService`.

Mirrors the structure of ``tests/unit/api/auth/test_user_service.py``: a
fake in-memory repository implements the :class:`ProjectRepository`
protocol, the service is constructed against it, and tests assert
behaviour + the audit event fired on each mutation.
"""

import pytest
import structlog

from synthorg.api.services.project_service import ProjectService
from synthorg.core.enums import ProjectStatus
from synthorg.core.project import Project
from synthorg.core.types import NotBlankStr
from synthorg.observability.events.api import (
    API_PROJECT_CREATED,
    API_PROJECT_DELETED,
    API_PROJECT_UPDATED,
)

pytestmark = pytest.mark.unit


class _FakeProjectRepo:
    """In-memory ProjectRepository used as a test stub."""

    def __init__(self) -> None:
        self._rows: dict[str, Project] = {}

    async def save(self, project: Project) -> None:
        self._rows[project.id] = project

    async def get(self, project_id: NotBlankStr) -> Project | None:
        return self._rows.get(project_id)

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        rows = sorted(self._rows.values(), key=lambda p: p.id)
        if status is not None:
            rows = [p for p in rows if p.status == status]
        if lead is not None:
            rows = [p for p in rows if p.lead == lead]
        return tuple(rows)

    async def delete(self, project_id: NotBlankStr) -> bool:
        return self._rows.pop(project_id, None) is not None


def _make_project(
    *,
    project_id: str = "proj-1",
    name: str = "Test project",
    lead: str = "agent-lead",
) -> Project:
    return Project(
        id=NotBlankStr(project_id),
        name=NotBlankStr(name),
        description="",
        team=(),
        lead=NotBlankStr(lead),
        deadline=None,
        budget=0.0,
    )


async def test_create_persists_and_emits_api_project_created() -> None:
    """``create`` saves the project and fires ``API_PROJECT_CREATED``.

    Asserts the structured kwargs (``project_id``, ``status``, ``lead``)
    so that a future refactor that drops a field from the audit payload
    is caught. Monitoring filters key on these fields.
    """
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)
    project = _make_project()

    with structlog.testing.capture_logs() as logs:
        result = await service.create(project)

    assert result == project
    fetched = await repo.get(project.id)
    assert fetched == project
    created_events = [log for log in logs if log["event"] == API_PROJECT_CREATED]
    assert len(created_events) == 1, (
        f"expected exactly one {API_PROJECT_CREATED} event in {logs}"
    )
    event = created_events[0]
    assert event["project_id"] == project.id
    assert event["status"] == project.status.value
    assert event["lead"] == project.lead


async def test_update_persists_and_emits_api_project_updated() -> None:
    """``update`` saves the project and fires ``API_PROJECT_UPDATED``.

    Asserts the structured kwargs (``project_id``, ``status``) to pin
    the audit payload shape against accidental field removal.
    """
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)
    project = _make_project()
    await repo.save(project)

    updated = project.model_copy(update={"name": NotBlankStr("Renamed")})
    with structlog.testing.capture_logs() as logs:
        await service.update(updated)

    fetched = await repo.get(project.id)
    assert fetched is not None
    assert fetched.name == "Renamed"
    updated_events = [log for log in logs if log["event"] == API_PROJECT_UPDATED]
    assert len(updated_events) == 1
    event = updated_events[0]
    assert event["project_id"] == updated.id
    assert event["status"] == updated.status.value


async def test_delete_returns_true_and_emits_api_project_deleted() -> None:
    """``delete`` returns ``True`` and emits ``API_PROJECT_DELETED``.

    Asserts ``project_id`` in the audit payload.
    """
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)
    project = _make_project()
    await repo.save(project)

    with structlog.testing.capture_logs() as logs:
        deleted = await service.delete(project.id)

    assert deleted is True
    assert await repo.get(project.id) is None
    deleted_events = [log for log in logs if log["event"] == API_PROJECT_DELETED]
    assert len(deleted_events) == 1
    assert deleted_events[0]["project_id"] == project.id


async def test_delete_returns_false_for_missing_and_does_not_emit_event() -> None:
    """Missing project: ``delete`` returns ``False``, no audit fired."""
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)

    with structlog.testing.capture_logs() as logs:
        deleted = await service.delete(NotBlankStr("proj-missing"))

    assert deleted is False
    assert not any(log["event"] == API_PROJECT_DELETED for log in logs)


async def test_get_passes_through_to_repo() -> None:
    """``get`` is a thin pass-through; no audit fired."""
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)
    project = _make_project()
    await repo.save(project)

    fetched = await service.get(project.id)
    assert fetched == project
    assert await service.get(NotBlankStr("proj-missing")) is None


async def test_list_projects_filters_by_status_and_lead() -> None:
    """``list_projects`` honours both filters and is order-stable."""
    repo = _FakeProjectRepo()
    service = ProjectService(repo=repo)
    p1 = _make_project(project_id="proj-1", lead="agent-a")
    p2 = _make_project(project_id="proj-2", lead="agent-b")
    await repo.save(p1)
    await repo.save(p2)

    by_lead = await service.list_projects(
        status=None,
        lead=NotBlankStr("agent-a"),
    )
    assert by_lead == (p1,)

    all_planning = await service.list_projects(
        status=ProjectStatus.PLANNING,
        lead=None,
    )
    # Default project status is PLANNING.
    assert set(all_planning) == {p1, p2}
