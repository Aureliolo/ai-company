"""Unit tests for meta-loop proposal appliers (apply + dry_run)."""

from typing import Any

import pytest

from synthorg.config.schema import RootConfig
from synthorg.meta.appliers.architecture_applier import (
    ArchitectureApplier,
    ArchitectureApplierContext,
)
from synthorg.meta.appliers.config_applier import ConfigApplier
from synthorg.meta.appliers.prompt_applier import (
    PromptApplier,
    PromptApplierContext,
)
from synthorg.meta.models import (
    ArchitectureChange,
    ConfigChange,
    EvolutionMode,
    ImprovementProposal,
    PromptChange,
    ProposalAltitude,
    ProposalRationale,
    RollbackOperation,
    RollbackPlan,
)

pytestmark = pytest.mark.unit


# -- Fixtures ----------------------------------------------------


def _rationale() -> ProposalRationale:
    return ProposalRationale(
        signal_summary="test",
        pattern_detected="test",
        expected_impact="test",
        confidence_reasoning="test",
    )


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        operations=(
            RollbackOperation(
                operation_type="revert",
                target="x",
                description="revert x",
            ),
        ),
        validation_check="check x",
    )


def _root_config() -> RootConfig:
    return RootConfig(company_name="Test Co")


def _config_provider() -> RootConfig:
    return _root_config()


def _proposal_config(
    *changes: ConfigChange,
) -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.CONFIG_TUNING,
        title="test",
        description="test",
        rationale=_rationale(),
        config_changes=changes,
        rollback_plan=_rollback(),
        confidence=0.8,
    )


def _proposal_prompt(
    *changes: PromptChange,
) -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.PROMPT_TUNING,
        title="test",
        description="test",
        rationale=_rationale(),
        prompt_changes=changes,
        rollback_plan=_rollback(),
        confidence=0.8,
    )


def _proposal_architecture(
    *changes: ArchitectureChange,
) -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.ARCHITECTURE,
        title="test",
        description="test",
        rationale=_rationale(),
        architecture_changes=changes,
        rollback_plan=_rollback(),
        confidence=0.8,
    )


# -- ConfigApplier ----------------------------------------------


class TestConfigApplier:
    def test_altitude(self) -> None:
        assert ConfigApplier().altitude == ProposalAltitude.CONFIG_TUNING

    async def test_apply_success(self) -> None:
        applier = ConfigApplier()
        proposal = _proposal_config(
            ConfigChange(
                path="a.b",
                old_value=1,
                new_value=2,
                description="d",
            ),
            ConfigChange(
                path="c.d",
                old_value=3,
                new_value=4,
                description="d",
            ),
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 2

    async def test_dry_run_without_provider_rejects(self) -> None:
        applier = ConfigApplier()
        proposal = _proposal_config(
            ConfigChange(
                path="company_name",
                new_value="New Name",
                description="rename",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "config_provider" in (result.error_message or "")

    async def test_dry_run_happy_path(self) -> None:
        applier = ConfigApplier(config_provider=_config_provider)
        proposal = _proposal_config(
            ConfigChange(
                path="company_name",
                old_value="Test Co",
                new_value="Renamed Co",
                description="rename",
            ),
        )
        result = await applier.dry_run(proposal)
        assert result.success, result.error_message
        assert result.changes_applied == 1

    async def test_dry_run_unknown_path_rejects(self) -> None:
        applier = ConfigApplier(config_provider=_config_provider)
        proposal = _proposal_config(
            ConfigChange(
                path="nonexistent.field",
                new_value=123,
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "unknown" in (result.error_message or "")

    async def test_dry_run_pydantic_validation_surfaces_errors(self) -> None:
        applier = ConfigApplier(config_provider=_config_provider)
        proposal = _proposal_config(
            ConfigChange(
                path="company_name",
                new_value="",
                description="invalid blank",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "company_name" in (result.error_message or "")

    async def test_dry_run_collects_all_errors(self) -> None:
        applier = ConfigApplier(config_provider=_config_provider)
        proposal = _proposal_config(
            ConfigChange(path="bogus.one", new_value=1, description="d"),
            ConfigChange(path="bogus.two", new_value=2, description="d"),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        message = result.error_message or ""
        assert "bogus.one" in message
        assert "bogus.two" in message

    async def test_dry_run_rejects_wrong_altitude(self) -> None:
        applier = ConfigApplier(config_provider=_config_provider)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="be concise and helpful",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "CONFIG_TUNING" in (result.error_message or "")


# -- PromptApplier ----------------------------------------------


class _FakePromptContext:
    def __init__(
        self,
        *,
        roles: frozenset[str] = frozenset(),
        departments: frozenset[str] = frozenset(),
        existing: dict[str, frozenset[str]] | None = None,
        overridden: frozenset[str] = frozenset(),
    ) -> None:
        self._roles = roles
        self._departments = departments
        self._existing = existing or {}
        self._overridden = overridden

    def known_roles(self) -> frozenset[str]:
        return self._roles

    def known_departments(self) -> frozenset[str]:
        return self._departments

    def existing_principles(self, scope: str) -> frozenset[str]:
        return self._existing.get(scope, frozenset())

    def scope_overridden(self, scope: str) -> bool:
        return scope in self._overridden


class TestPromptApplier:
    def test_altitude(self) -> None:
        assert PromptApplier().altitude == ProposalAltitude.PROMPT_TUNING

    def test_context_protocol_conformance(self) -> None:
        assert isinstance(_FakePromptContext(), PromptApplierContext)

    async def test_apply_success(self) -> None:
        applier = PromptApplier()
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="be concise and helpful",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 1

    async def test_dry_run_without_context_rejects(self) -> None:
        applier = PromptApplier()
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="be concise and helpful",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "PromptApplierContext" in (result.error_message or "")

    async def test_dry_run_happy_path(self) -> None:
        context = _FakePromptContext(
            roles=frozenset({"engineer"}),
            departments=frozenset({"engineering"}),
        )
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="Be concise and helpful always.",
                target_scope="all",
                description="d",
            ),
            PromptChange(
                principle_text="Engineers must cite source files.",
                target_scope="engineer",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert result.success, result.error_message
        assert result.changes_applied == 2

    async def test_dry_run_unknown_scope(self) -> None:
        context = _FakePromptContext()
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="Be concise and helpful always.",
                target_scope="unknown_role",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "Unknown target_scope" in (result.error_message or "")

    async def test_dry_run_principle_too_short(self) -> None:
        context = _FakePromptContext()
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="too shrt",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "too short" in (result.error_message or "")

    async def test_dry_run_principle_too_long(self) -> None:
        context = _FakePromptContext()
        applier = PromptApplier(context=context)
        long_text = "x" * 5000
        proposal = _proposal_prompt(
            PromptChange(
                principle_text=long_text,
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "too long" in (result.error_message or "")

    async def test_dry_run_duplicate_in_proposal(self) -> None:
        context = _FakePromptContext()
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="Be concise and helpful.",
                target_scope="all",
                description="d",
            ),
            PromptChange(
                principle_text="  Be Concise and Helpful.  ",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "Duplicate principle_text" in (result.error_message or "")

    async def test_dry_run_duplicate_with_existing(self) -> None:
        context = _FakePromptContext(
            existing={"all": frozenset({"be concise and helpful."})},
        )
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="Be concise and helpful.",
                target_scope="all",
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "already exists" in (result.error_message or "")

    async def test_dry_run_override_conflict(self) -> None:
        context = _FakePromptContext(overridden=frozenset({"all"}))
        applier = PromptApplier(context=context)
        proposal = _proposal_prompt(
            PromptChange(
                principle_text="Be concise and helpful always.",
                target_scope="all",
                evolution_mode=EvolutionMode.OVERRIDE,
                description="d",
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "active OVERRIDE" in (result.error_message or "")


# -- ArchitectureApplier -----------------------------------------


class _FakeArchContext:
    def __init__(
        self,
        *,
        roles: frozenset[str] = frozenset(),
        departments: frozenset[str] = frozenset(),
        workflows: frozenset[str] = frozenset(),
        roles_in_use: frozenset[str] = frozenset(),
        depts_in_use: frozenset[str] = frozenset(),
    ) -> None:
        self._roles = roles
        self._departments = departments
        self._workflows = workflows
        self._roles_in_use = roles_in_use
        self._depts_in_use = depts_in_use

    def has_role(self, name: str) -> bool:
        return name in self._roles

    def has_department(self, name: str) -> bool:
        return name in self._departments

    def has_workflow(self, name: str) -> bool:
        return name in self._workflows

    def role_in_use(self, name: str) -> bool:
        return name in self._roles_in_use

    def department_in_use(self, name: str) -> bool:
        return name in self._depts_in_use


def _arch(
    operation: str,
    target_name: str,
    *,
    payload: dict[str, Any] | None = None,
) -> ArchitectureChange:
    return ArchitectureChange(
        operation=operation,
        target_name=target_name,
        payload=payload or {},
        description="d",
    )


class TestArchitectureApplier:
    def test_altitude(self) -> None:
        assert ArchitectureApplier().altitude == ProposalAltitude.ARCHITECTURE

    def test_context_protocol_conformance(self) -> None:
        assert isinstance(_FakeArchContext(), ArchitectureApplierContext)

    async def test_apply_success(self) -> None:
        applier = ArchitectureApplier()
        proposal = _proposal_architecture(
            _arch("create_role", "new-role", payload={"description": "d"}),
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 1

    async def test_dry_run_without_context_rejects(self) -> None:
        applier = ArchitectureApplier()
        proposal = _proposal_architecture(
            _arch("create_role", "new-role", payload={"description": "d"}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "ArchitectureApplierContext" in (result.error_message or "")

    async def test_dry_run_unknown_operation(self) -> None:
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch("nonsense_op", "new-role", payload={"description": "d"}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "Unknown operation" in (result.error_message or "")

    async def test_dry_run_create_role_happy_path(self) -> None:
        context = _FakeArchContext(departments=frozenset({"engineering"}))
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "senior-engineer",
                payload={
                    "description": "d",
                    "department": "engineering",
                    "required_skills": ["python"],
                },
            ),
        )
        result = await applier.dry_run(proposal)
        assert result.success, result.error_message

    async def test_dry_run_create_role_duplicate_name(self) -> None:
        context = _FakeArchContext(roles=frozenset({"engineer"}))
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch("create_role", "engineer", payload={"description": "d"}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "already exists" in (result.error_message or "")

    async def test_dry_run_create_role_missing_required_key(self) -> None:
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch("create_role", "new-role", payload={}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "missing required" in (result.error_message or "")

    async def test_dry_run_create_role_unknown_department(self) -> None:
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "new-role",
                payload={
                    "description": "d",
                    "department": "nonexistent",
                },
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "department" in (result.error_message or "")

    async def test_dry_run_modify_workflow_missing(self) -> None:
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch("modify_workflow", "wf-1", payload={"field": "value"}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "does not exist" in (result.error_message or "")

    async def test_dry_run_modify_workflow_empty_payload(self) -> None:
        context = _FakeArchContext(workflows=frozenset({"wf-1"}))
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch("modify_workflow", "wf-1", payload={}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "no-op modify" in (result.error_message or "")

    async def test_dry_run_remove_role_in_use(self) -> None:
        context = _FakeArchContext(
            roles=frozenset({"engineer"}),
            roles_in_use=frozenset({"engineer"}),
        )
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch("remove_role", "engineer", payload={}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "still referenced" in (result.error_message or "")

    async def test_dry_run_remove_department_in_use(self) -> None:
        context = _FakeArchContext(
            departments=frozenset({"engineering"}),
            depts_in_use=frozenset({"engineering"}),
        )
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch("remove_department", "engineering", payload={}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "still referenced" in (result.error_message or "")

    async def test_dry_run_collects_all_errors(self) -> None:
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch("create_role", "a", payload={}),
            _arch("remove_role", "nonexistent", payload={}),
            _arch("modify_workflow", "nowhere", payload={"x": 1}),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        message = result.error_message or ""
        assert "missing required" in message
        assert "remove_role" in message
        assert "modify_workflow" in message

    async def test_dry_run_in_proposal_dependencies_resolve(self) -> None:
        context = _FakeArchContext()
        applier = ArchitectureApplier(context=context)
        proposal = _proposal_architecture(
            _arch("create_department", "eng", payload={}),
            _arch(
                "create_role",
                "senior-engineer",
                payload={"description": "d", "department": "eng"},
            ),
        )
        result = await applier.dry_run(proposal)
        assert result.success, result.error_message

    async def test_dry_run_description_length_cap(self) -> None:
        """A description exceeding the 2000-char cap is rejected."""
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "new-role",
                payload={"description": "d" * 3_000},
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "'description' exceeds" in (result.error_message or "")

    async def test_dry_run_skill_name_length_cap(self) -> None:
        """A skill name exceeding the 80-char cap is rejected."""
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "new-role",
                payload={
                    "description": "d",
                    "required_skills": ["x" * 200],
                },
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "required_skills[0]" in (result.error_message or "")

    async def test_dry_run_skill_count_cap(self) -> None:
        """More than 100 skills is rejected."""
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "new-role",
                payload={
                    "description": "d",
                    "required_skills": [f"s{i}" for i in range(150)],
                },
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "exceeds" in (result.error_message or "")

    async def test_dry_run_non_string_skill_rejected(self) -> None:
        """Non-string skill entries are rejected."""
        applier = ArchitectureApplier(context=_FakeArchContext())
        proposal = _proposal_architecture(
            _arch(
                "create_role",
                "new-role",
                payload={
                    "description": "d",
                    "required_skills": ["python", 42, "go"],
                },
            ),
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert "required_skills[1]" in (result.error_message or "")
        assert "must be a string" in (result.error_message or "")
