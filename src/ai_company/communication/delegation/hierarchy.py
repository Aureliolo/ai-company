"""Hierarchy resolver for organizational structure."""

from ai_company.communication.errors import HierarchyResolutionError
from ai_company.core.company import Company  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.delegation import (
    DELEGATION_HIERARCHY_BUILT,
    DELEGATION_HIERARCHY_CYCLE,
)

logger = get_logger(__name__)


class HierarchyResolver:
    """Resolves org hierarchy from a Company structure (read-only).

    Built from three sources, in priority order:

    1. Explicit ``ReportingLine.supervisor`` (most specific)
    2. ``Team.lead`` for team members
    3. ``Department.head`` for team leads without explicit reporting

    Detects cycles at construction time.

    Args:
        company: Frozen company structure to resolve hierarchy from.

    Raises:
        HierarchyResolutionError: If a cycle is detected.
    """

    __slots__ = ("_reports_of", "_supervisor_of")

    def __init__(self, company: Company) -> None:
        supervisor_of: dict[str, str] = {}
        reports_of: dict[str, list[str]] = {}

        for dept in company.departments:
            for team in dept.teams:
                # Team lead → department head (lowest priority)
                if team.lead not in supervisor_of:
                    supervisor_of[team.lead] = dept.head
                    reports_of.setdefault(dept.head, []).append(team.lead)

                # Team members → team lead (medium priority)
                for member in team.members:
                    if member == team.lead:
                        continue
                    if member not in supervisor_of:
                        supervisor_of[member] = team.lead
                        reports_of.setdefault(team.lead, []).append(member)

            # Explicit reporting lines (highest priority — override)
            for line in dept.reporting_lines:
                old_sup = supervisor_of.get(line.subordinate)
                if old_sup is not None and old_sup != line.supervisor:
                    # Remove from old supervisor's reports
                    old_reports = reports_of.get(old_sup, [])
                    if line.subordinate in old_reports:
                        old_reports.remove(line.subordinate)
                supervisor_of[line.subordinate] = line.supervisor
                reports_of.setdefault(line.supervisor, []).append(line.subordinate)

        # Cycle detection
        self._detect_cycles(supervisor_of)

        # Freeze internal state
        self._supervisor_of: dict[str, str] = supervisor_of
        self._reports_of: dict[str, tuple[str, ...]] = {
            k: tuple(v) for k, v in reports_of.items()
        }

        logger.debug(
            DELEGATION_HIERARCHY_BUILT,
            agents=len(supervisor_of),
            supervisors=len(reports_of),
        )

    @staticmethod
    def _detect_cycles(supervisor_of: dict[str, str]) -> None:
        """Detect cycles in the supervisor graph.

        Args:
            supervisor_of: Mapping from agent to supervisor.

        Raises:
            HierarchyResolutionError: If a cycle is found.
        """
        for agent in supervisor_of:
            visited: set[str] = set()
            current = agent
            while current in supervisor_of:
                if current in visited:
                    logger.warning(
                        DELEGATION_HIERARCHY_CYCLE,
                        agent=agent,
                        cycle_at=current,
                    )
                    msg = (
                        f"Cycle detected in hierarchy at "
                        f"{current!r} (starting from {agent!r})"
                    )
                    raise HierarchyResolutionError(
                        msg,
                        context={
                            "agent": agent,
                            "cycle_at": current,
                        },
                    )
                visited.add(current)
                current = supervisor_of[current]

    def get_supervisor(self, agent_name: str) -> str | None:
        """Get the direct supervisor of an agent.

        Args:
            agent_name: Agent name to look up.

        Returns:
            Supervisor name or None if the agent is at the top.
        """
        return self._supervisor_of.get(agent_name)

    def get_direct_reports(
        self,
        agent_name: str,
    ) -> tuple[str, ...]:
        """Get all direct reports of an agent.

        Args:
            agent_name: Supervisor agent name.

        Returns:
            Tuple of direct report agent names.
        """
        return self._reports_of.get(agent_name, ())

    def is_direct_report(
        self,
        supervisor: str,
        subordinate: str,
    ) -> bool:
        """Check if subordinate directly reports to supervisor.

        Args:
            supervisor: Supervisor agent name.
            subordinate: Potential subordinate agent name.

        Returns:
            True if subordinate is a direct report.
        """
        return subordinate in self.get_direct_reports(supervisor)

    def is_subordinate(
        self,
        supervisor: str,
        subordinate: str,
    ) -> bool:
        """Check if subordinate is anywhere below supervisor.

        Walks up the hierarchy from subordinate to root.

        Args:
            supervisor: Supervisor agent name.
            subordinate: Potential subordinate agent name.

        Returns:
            True if subordinate is below supervisor at any depth.
        """
        current = subordinate
        while current in self._supervisor_of:
            current = self._supervisor_of[current]
            if current == supervisor:
                return True
        return False

    def get_ancestors(self, agent_name: str) -> tuple[str, ...]:
        """Get all ancestors from agent up to root.

        Args:
            agent_name: Agent to start from.

        Returns:
            Tuple of ancestor names, bottom-up (immediate supervisor
            first, root last).
        """
        ancestors: list[str] = []
        current = agent_name
        while current in self._supervisor_of:
            current = self._supervisor_of[current]
            ancestors.append(current)
        return tuple(ancestors)

    def get_delegation_depth(
        self,
        from_agent: str,
        to_agent: str,
    ) -> int | None:
        """Get hierarchy levels between two agents.

        Args:
            from_agent: Higher-level agent (potential supervisor).
            to_agent: Lower-level agent (potential subordinate).

        Returns:
            Number of hierarchy levels between them, or None if
            to_agent is not below from_agent.
        """
        depth = 0
        current = to_agent
        while current in self._supervisor_of:
            current = self._supervisor_of[current]
            depth += 1
            if current == from_agent:
                return depth
        return None
