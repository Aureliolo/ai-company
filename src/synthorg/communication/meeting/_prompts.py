"""Shared prompt builders for meeting protocol implementations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.communication.meeting.models import MeetingAgenda


def build_agenda_prompt(agenda: MeetingAgenda) -> str:
    """Build the initial agenda prompt text.

    Args:
        agenda: The meeting agenda to format.

    Returns:
        Formatted agenda text for use in agent prompts.
    """
    parts = [f"Meeting: {agenda.title}"]
    if agenda.context:
        parts.append(f"Context: {agenda.context}")
    if agenda.items:
        parts.append("Agenda items:")
        for i, item in enumerate(agenda.items, 1):
            entry = f"  {i}. {item.title}"
            if item.description:
                entry += f" -- {item.description}"
            if item.presenter_id:
                entry += f" (presenter: {item.presenter_id})"
            parts.append(entry)
    return "\n".join(parts)


def inject_lens_perspective(
    prompt: str,
    agent_id: str,
    lens_assignments: dict[str, str] | None,
) -> str:
    """Append lens perspective instructions to a prompt.

    If the agent has a lens assignment, the lens name is appended
    as a perspective instruction.  Otherwise the prompt is returned
    unchanged.

    Args:
        prompt: The base prompt text.
        agent_id: The agent to look up in assignments.
        lens_assignments: Optional mapping of agent ID to lens name.

    Returns:
        The prompt, optionally extended with lens instructions.
    """
    if not lens_assignments or agent_id not in lens_assignments:
        return prompt
    lens_name = lens_assignments[agent_id]
    return (
        f"{prompt}\n\n"
        f"[Strategic Lens: {lens_name}]\n"
        f"Adopt the {lens_name} perspective in your analysis. "
        f"Evaluate the agenda items through this specific lens."
    )
