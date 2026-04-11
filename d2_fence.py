"""Standalone D2 fence formatter for zensical builds.

Zensical does not run mkdocs plugin lifecycle hooks, so mkdocs-d2-plugin's
``on_config`` hook (which registers the D2 custom fence in pymdownx.superfences)
never fires. This module exposes ``validator`` and ``formatter`` at module level
so they can be referenced directly in ``mkdocs.yml`` via ``!!python/name:``.

Configuration is sourced from ``mkdocs.yml`` at import time via
``zensical.config.get_config()``.
"""

import subprocess
from functools import partial

from d2.fence import D2CustomFence
from d2.plugin import render as _render

_D2_NOT_FOUND = (
    "D2 executable not found on PATH. Install from https://d2lang.com/tour/install"
)


def _build_fence() -> D2CustomFence:
    """Build a D2CustomFence from mkdocs.yml plugin config."""
    from zensical.config import get_config  # noqa: PLC0415

    cfg = get_config()
    d2_cfg = cfg.get("plugins", {}).get("d2", {})
    if isinstance(d2_cfg, dict) and "config" in d2_cfg:
        d2_cfg = d2_cfg["config"]

    executable = d2_cfg.pop("executable", "d2")
    d2_cfg.pop("cache", None)
    d2_cfg.pop("cache_dir", None)

    # Defaults matching mkdocs.yml plugin config
    d2_cfg.setdefault("layout", "dagre")
    d2_cfg.setdefault("theme", 200)
    d2_cfg.setdefault("dark_theme", -1)
    d2_cfg.setdefault("sketch", False)
    d2_cfg.setdefault("pad", 100)
    d2_cfg.setdefault("scale", -1.0)
    d2_cfg.setdefault("force_appendix", False)
    d2_cfg.setdefault("target", "''")

    # Verify binary is available
    try:
        subprocess.run(  # noqa: S603
            [executable, "--version"], capture_output=True, check=True
        )
    except FileNotFoundError:
        raise RuntimeError(_D2_NOT_FOUND) from None

    renderer = partial(_render, executable, None)
    return D2CustomFence(d2_cfg, renderer)


_fence = _build_fence()
validator = _fence.validator
formatter = _fence.formatter
