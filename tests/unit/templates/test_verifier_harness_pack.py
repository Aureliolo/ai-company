"""Tests for the verifier-harness template pack."""

from pathlib import Path

import pytest
import yaml


def _load_pack() -> dict:
    pack_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "synthorg"
        / "templates"
        / "packs"
        / "verifier-harness.yaml"
    )
    with pack_path.open() as f:
        return yaml.safe_load(f)


@pytest.mark.unit
class TestVerifierHarnessPack:
    def test_has_three_agents(self) -> None:
        data = _load_pack()
        agents = data["template"]["agents"]
        assert len(agents) == 3

    def test_agent_roles(self) -> None:
        data = _load_pack()
        roles = {a["role"] for a in data["template"]["agents"]}
        assert roles == {"Planner", "Generator", "Evaluator"}

    def test_evaluator_is_not_generator(self) -> None:
        data = _load_pack()
        agents = data["template"]["agents"]
        evaluator = next(a for a in agents if a["role"] == "Evaluator")
        generator = next(a for a in agents if a["role"] == "Generator")
        assert evaluator["role"] != generator["role"]

    def test_has_verification_tag(self) -> None:
        data = _load_pack()
        tags = data["template"]["tags"]
        assert "verification" in tags

    def test_min_max_agents(self) -> None:
        data = _load_pack()
        assert data["template"]["min_agents"] == 3
        assert data["template"]["max_agents"] == 3

    def test_evaluator_uses_quality_guardian_preset(self) -> None:
        data = _load_pack()
        agents = data["template"]["agents"]
        evaluator = next(a for a in agents if a["role"] == "Evaluator")
        assert evaluator["personality_preset"] == "quality_guardian"
