"""Tests for uses_packs template composition."""

import pytest

from synthorg.templates.schema import CompanyTemplate


@pytest.mark.unit
class TestUsesPacksField:
    """Tests for the uses_packs field on CompanyTemplate."""

    def test_defaults_to_empty(self, make_template_dict: object) -> None:
        data = make_template_dict()  # type: ignore[operator]
        tmpl = CompanyTemplate(**data)
        assert tmpl.uses_packs == ()

    def test_accepts_pack_names(self, make_template_dict: object) -> None:
        data = make_template_dict(  # type: ignore[operator]
            uses_packs=("security-team", "data-team"),
        )
        tmpl = CompanyTemplate(**data)
        assert tmpl.uses_packs == ("security-team", "data-team")

    def test_skips_agent_count_validation_with_packs(
        self, make_template_dict: object
    ) -> None:
        """Templates with uses_packs can have zero agents."""
        data = make_template_dict(  # type: ignore[operator]
            agents=(),
            uses_packs=("security-team",),
        )
        # Should not raise even though agents is empty
        tmpl = CompanyTemplate(**data)
        assert len(tmpl.agents) == 0


@pytest.mark.unit
class TestUsesPacksRendering:
    """Tests for uses_packs resolution in the renderer."""

    def test_pack_agents_merged(self, tmp_path: pytest.TempPathFactory) -> None:
        """A template using a pack gets the pack's agents."""
        from synthorg.templates.loader import LoadedTemplate, _parse_template_yaml
        from synthorg.templates.renderer import render_template

        yaml_text = """\
template:
  name: "With Security Pack"
  description: "Uses security-team pack"
  version: "1.0.0"
  min_agents: 1
  max_agents: 20
  uses_packs:
    - "security-team"

  company:
    type: "custom"

  agents:
    - role: "Backend Developer"
      name: "Dev One"
      level: "mid"
      model: "medium"
      department: "engineering"

  departments:
    - name: "engineering"
      budget_percent: 80
      head_role: "Backend Developer"
"""
        template = _parse_template_yaml(yaml_text, source_name="<test>")
        loaded = LoadedTemplate(
            template=template, raw_yaml=yaml_text, source_name="<test>"
        )
        config = render_template(loaded)

        # Should have the template's own agent + the pack's agents
        roles = {a.role for a in config.agents}
        assert "Backend Developer" in roles
        assert "Security Engineer" in roles
        assert "Security Operations" in roles

    def test_pack_departments_merged(self) -> None:
        """A template using a pack gets the pack's departments."""
        from synthorg.templates.loader import LoadedTemplate, _parse_template_yaml
        from synthorg.templates.renderer import render_template

        yaml_text = """\
template:
  name: "With Data Pack"
  description: "Uses data-team pack"
  version: "1.0.0"
  min_agents: 1
  max_agents: 20
  uses_packs:
    - "data-team"

  company:
    type: "custom"

  agents:
    - role: "CEO"
      name: "Boss"
      level: "c_suite"
      model: "large"
      department: "executive"

  departments:
    - name: "executive"
      budget_percent: 20
      head_role: "CEO"
"""
        template = _parse_template_yaml(yaml_text, source_name="<test>")
        loaded = LoadedTemplate(
            template=template, raw_yaml=yaml_text, source_name="<test>"
        )
        config = render_template(loaded)

        dept_names = {d.name for d in config.departments}
        assert "executive" in dept_names
        assert "data_analytics" in dept_names

    def test_child_wins_over_pack(self) -> None:
        """Child's own fields override pack fields."""
        from synthorg.templates.loader import LoadedTemplate, _parse_template_yaml
        from synthorg.templates.renderer import render_template

        yaml_text = """\
template:
  name: "Override Pack"
  description: "Overrides security dept budget"
  version: "1.0.0"
  min_agents: 1
  max_agents: 20
  uses_packs:
    - "security-team"

  company:
    type: "custom"

  departments:
    - name: "security"
      budget_percent: 25
      head_role: "Security Engineer"

  agents:
    - role: "Backend Developer"
      name: "Dev"
      level: "mid"
      model: "medium"
      department: "engineering"
"""
        template = _parse_template_yaml(yaml_text, source_name="<test>")
        loaded = LoadedTemplate(
            template=template, raw_yaml=yaml_text, source_name="<test>"
        )
        config = render_template(loaded)

        sec_dept = next(d for d in config.departments if d.name == "security")
        assert sec_dept.budget_percent == 25.0

    def test_backward_compatible(self) -> None:
        """Templates without uses_packs render identically."""
        from synthorg.templates import load_template, render_template

        loaded = load_template("startup")
        config = render_template(loaded)

        # Startup has 5 agents and 3 departments (exec, eng, product)
        assert len(config.agents) == 5
        assert len(config.departments) == 3
