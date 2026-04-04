"""Tests for SQLite schema application."""

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from synthorg.persistence.errors import MigrationError
from synthorg.persistence.sqlite.migrations import apply_schema

if TYPE_CHECKING:
    import aiosqlite

_EXPECTED_TABLES = {
    "tasks",
    "cost_records",
    "messages",
    "lifecycle_events",
    "task_metrics",
    "collaboration_metrics",
    "parked_contexts",
    "audit_entries",
    "settings",
    "users",
    "api_keys",
    "sessions",
    "checkpoints",
    "heartbeats",
    "agent_states",
    "artifacts",
    "projects",
    "custom_presets",
    "workflow_definitions",
    "workflow_definition_versions",
    "workflow_executions",
    "fine_tune_runs",
    "fine_tune_checkpoints",
}

_EXPECTED_INDEXES = {
    "idx_tasks_status",
    "idx_tasks_assigned_to",
    "idx_tasks_project",
    "idx_cost_records_agent_id",
    "idx_cost_records_task_id",
    "idx_messages_channel",
    "idx_messages_timestamp",
    "idx_le_agent_id",
    "idx_le_event_type",
    "idx_le_timestamp",
    "idx_tm_agent_id",
    "idx_tm_completed_at",
    "idx_tm_agent_completed",
    "idx_cm_agent_id",
    "idx_cm_recorded_at",
    "idx_cm_agent_recorded",
    "idx_pc_agent_id",
    "idx_pc_approval_id",
    "idx_ae_timestamp",
    "idx_ae_agent_id",
    "idx_users_role",
    "idx_single_ceo",
    "idx_ae_action_type",
    "idx_ae_verdict",
    "idx_ae_risk_level",
    "idx_api_keys_user_id",
    "idx_sessions_user_revoked_expires",
    "idx_sessions_revoked_expires",
    "idx_sessions_expires_at",
    "idx_cp_execution_id",
    "idx_cp_task_id",
    "idx_cp_exec_turn",
    "idx_cp_task_turn",
    "idx_hb_last_heartbeat",
    "idx_as_status_activity",
    "idx_artifacts_task_id",
    "idx_artifacts_created_by",
    "idx_artifacts_type",
    "idx_projects_status",
    "idx_projects_lead",
    "idx_wd_workflow_type",
    "idx_wd_updated_at",
    "idx_wfe_definition_id",
    "idx_wfe_status",
    "idx_wfe_updated_at",
    "idx_wfe_definition_updated",
    "idx_wfe_status_updated",
    "idx_wfe_project",
    "idx_ftr_stage",
    "idx_ftr_started_at",
    "idx_ftr_updated_at",
    "idx_ftc_run_id",
    "idx_ftc_active",
    "idx_ftc_single_active",
    "idx_ftc_created_at",
    "idx_wdv_definition_saved",
}


@pytest.mark.unit
class TestApplySchema:
    """Tests for apply_schema()."""

    async def test_creates_all_tables(self, memory_db: aiosqlite.Connection) -> None:
        await apply_schema(memory_db)

        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert tables == _EXPECTED_TABLES

    async def test_creates_all_indexes(self, memory_db: aiosqlite.Connection) -> None:
        await apply_schema(memory_db)

        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_%' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert indexes == _EXPECTED_INDEXES

    async def test_idempotent(self, memory_db: aiosqlite.Connection) -> None:
        """Applying the schema twice does not raise."""
        await apply_schema(memory_db)
        await apply_schema(memory_db)

        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert tables == _EXPECTED_TABLES

    async def test_parked_contexts_task_id_is_nullable(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """parked_contexts.task_id allows NULL."""
        await apply_schema(memory_db)
        cursor = await memory_db.execute("PRAGMA table_info('parked_contexts')")
        columns = {row[1]: row[3] for row in await cursor.fetchall()}
        # notnull == 0 means nullable
        assert columns["task_id"] == 0

    async def test_settings_has_composite_key(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """settings table has namespace + key as composite primary key."""
        await apply_schema(memory_db)
        cursor = await memory_db.execute("PRAGMA table_info('settings')")
        rows = await cursor.fetchall()
        columns = {row[1] for row in rows}
        assert {"namespace", "key", "value", "updated_at"} == columns
        # row[5] is the pk ordinal (1-based); 0 means not part of PK.
        pk_columns = {row[1]: row[5] for row in rows}
        assert pk_columns["namespace"] == 1
        assert pk_columns["key"] == 2

    async def test_agent_states_ddl_has_check_constraints(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """DDL includes CHECK constraints for status, counters, and invariant."""
        await apply_schema(memory_db)
        cursor = await memory_db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_states'"
        )
        row = await cursor.fetchone()
        assert row is not None
        ddl = row[0]
        assert "CHECK (status IN ('idle', 'executing', 'paused'))" in ddl
        assert "CHECK (turn_count >= 0)" in ddl
        assert "CHECK (accumulated_cost_usd >= 0.0)" in ddl
        assert "status = 'idle'" in ddl
        assert "execution_id IS NULL" in ddl
        assert "started_at IS NOT NULL" in ddl

    async def test_agent_states_rejects_invalid_status(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """CHECK constraint rejects invalid status values."""
        await apply_schema(memory_db)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            await memory_db.execute(
                "INSERT INTO agent_states "
                "(agent_id, status, last_activity_at) "
                "VALUES (?, ?, ?)",
                ("a", "invalid", "2026-01-01T00:00:00+00:00"),
            )

    async def test_failure_raises_migration_error(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """Schema application failure wraps as MigrationError."""
        with (
            patch(
                "synthorg.persistence.sqlite.migrations.importlib.resources.files",
                side_effect=OSError("simulated read failure"),
            ),
            pytest.raises(MigrationError, match="Failed to apply schema"),
        ):
            await apply_schema(memory_db)
