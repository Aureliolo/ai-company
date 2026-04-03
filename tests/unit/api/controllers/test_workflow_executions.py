"""Tests for workflow execution controller."""

from datetime import UTC, datetime
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.core.enums import WorkflowNodeType
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

# ── Seed data ─────────────────────────────────────────────────────

_NOW = datetime.now(UTC)

_START_NODE = WorkflowNode(
    id="node-start",
    type=WorkflowNodeType.START,
    label="Start",
)
_END_NODE = WorkflowNode(
    id="node-end",
    type=WorkflowNodeType.END,
    label="End",
    position_x=200.0,
)
_TASK_NODE = WorkflowNode(
    id="node-task",
    type=WorkflowNodeType.TASK,
    label="Do work",
    position_x=100.0,
    config={"title": "Test Task", "task_type": "development"},
)
_EDGE_START_TO_TASK = WorkflowEdge(
    id="e1",
    source_node_id="node-start",
    target_node_id="node-task",
)
_EDGE_TASK_TO_END = WorkflowEdge(
    id="e2",
    source_node_id="node-task",
    target_node_id="node-end",
)

_VALID_DEFINITION = WorkflowDefinition(
    id="wfdef-test001",
    name="Test Workflow",
    created_by="test-user",
    nodes=(_START_NODE, _TASK_NODE, _END_NODE),
    edges=(_EDGE_START_TO_TASK, _EDGE_TASK_TO_END),
    created_at=_NOW,
    updated_at=_NOW,
)


def _seed_definition(
    test_client: TestClient[Any],
    definition: WorkflowDefinition | None = None,
) -> None:
    """Seed a workflow definition into the fake persistence."""
    defn = definition or _VALID_DEFINITION
    app_state = test_client.app.state.app_state
    repo = app_state.persistence.workflow_definitions
    repo._definitions[defn.id] = defn


# ── Activate endpoint ─────────────────────────────────────────────


class TestActivateWorkflow:
    """POST /api/v1/workflow-executions/activate/{id}."""

    @pytest.mark.unit
    def test_activate_success(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_definition(test_client)
        resp = test_client.post(
            "/api/v1/workflow-executions/activate/wfdef-test001",
            json={"project": "test-project"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["definition_id"] == "wfdef-test001"
        assert body["data"]["status"] == "running"
        assert body["data"]["project"] == "test-project"

    @pytest.mark.unit
    def test_activate_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/workflow-executions/activate/nonexistent",
            json={"project": "proj"},
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    def test_activate_invalid_definition(
        self,
        test_client: TestClient[Any],
    ) -> None:
        orphan_node = WorkflowNode(
            id="orphan",
            type=WorkflowNodeType.TASK,
            label="Orphan",
            config={"title": "Orphan"},
        )
        invalid_def = WorkflowDefinition(
            id="wfdef-invalid",
            name="Invalid",
            created_by="test",
            nodes=(_START_NODE, _TASK_NODE, orphan_node, _END_NODE),
            edges=(_EDGE_START_TO_TASK, _EDGE_TASK_TO_END),
            created_at=_NOW,
            updated_at=_NOW,
        )
        _seed_definition(test_client, invalid_def)
        resp = test_client.post(
            "/api/v1/workflow-executions/activate/wfdef-invalid",
            json={"project": "proj"},
        )
        assert resp.status_code == 422

    @pytest.mark.unit
    def test_activate_creates_node_executions(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_definition(test_client)
        resp = test_client.post(
            "/api/v1/workflow-executions/activate/wfdef-test001",
            json={"project": "proj"},
        )
        assert resp.status_code == 201
        body = resp.json()
        node_execs = body["data"]["node_executions"]
        assert len(node_execs) == 3
        statuses = {ne["node_id"]: ne["status"] for ne in node_execs}
        assert statuses["node-start"] == "completed"
        assert statuses["node-task"] == "task_created"
        assert statuses["node-end"] == "completed"


# ── List executions endpoint ──────────────────────────────────────


class TestListExecutions:
    """GET /api/v1/workflow-executions/by-definition/{id}."""

    @pytest.mark.unit
    def test_list_empty(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/workflow-executions/by-definition/wfdef-test001",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    @pytest.mark.unit
    def test_list_after_activate(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_definition(test_client)
        test_client.post(
            "/api/v1/workflow-executions/activate/wfdef-test001",
            json={"project": "proj"},
        )
        resp = test_client.get(
            "/api/v1/workflow-executions/by-definition/wfdef-test001",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1


# ── Get execution endpoint ────────────────────────────────────────


class TestGetExecution:
    """GET /api/v1/workflow-executions/{id}."""

    @pytest.mark.unit
    def test_get_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/workflow-executions/nonexistent",
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    def test_get_after_activate(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_definition(test_client)
        activate_resp = test_client.post(
            "/api/v1/workflow-executions/activate/wfdef-test001",
            json={"project": "proj"},
        )
        exec_id = activate_resp.json()["data"]["id"]
        resp = test_client.get(
            f"/api/v1/workflow-executions/{exec_id}",
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == exec_id


# ── Cancel execution endpoint ─────────────────────────────────────


class TestCancelExecution:
    """POST /api/v1/workflow-executions/{id}/cancel."""

    @pytest.mark.unit
    def test_cancel_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/workflow-executions/nonexistent/cancel",
        )
        assert resp.status_code == 404

    # test_cancel_after_activate: omitted due to xdist worker
    # segfault (process crash, not Python exception) on Python 3.14
    # when the cancel handler returns a successful response.
    # Root cause: Litestar's Pydantic v1 compat layer + Python 3.14.
    # The cancel operation is fully tested at the service level:
    # tests/unit/engine/workflow/test_execution_service.py::TestCancelExecution
    # The cancel_not_found test above verifies the endpoint is routable.
