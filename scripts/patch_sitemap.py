"""Append static OpenAPI artifact URLs to the built docs sitemap.

Zensical generates ``_site/docs/sitemap.xml`` from Markdown pages only.
The interactive Scalar viewer (``reference.html``) and the raw OpenAPI
schema (``openapi.json``) are copied into the output as static assets
and therefore don't appear in the generated sitemap.

This script patches the built sitemap to add explicit ``<url>`` entries
for those two artifacts so search engines can discover them.

Run after ``zensical build``:

    uv run python scripts/export_openapi.py
    uv run zensical build
    uv run python scripts/patch_sitemap.py

CI (``pages.yml``, ``pages-preview.yml``) runs the same sequence before
deploying the docs site.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_FILE = REPO_ROOT / "_site" / "docs" / "sitemap.xml"

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Static artifacts that should be discoverable but live outside the
# Markdown-driven nav tree. Paths are absolute URLs on the deployed site.
EXTRA_URLS: tuple[str, ...] = (
    "https://synthorg.io/docs/openapi/reference.html",
    "https://synthorg.io/docs/openapi/openapi.json",
)


def main() -> int:
    """Insert EXTRA_URLS into the built sitemap, idempotent on rerun."""
    if not SITEMAP_FILE.exists():
        print(
            f"Error: sitemap not found at {SITEMAP_FILE.relative_to(REPO_ROOT)}",
            file=sys.stderr,
        )
        print(
            "Run `uv run zensical build` first to generate the sitemap.",
            file=sys.stderr,
        )
        return 1

    # Register the default namespace BEFORE parsing so ElementTree
    # emits clean `<url>` tags instead of `<ns0:url>` on write.
    ET.register_namespace("", SITEMAP_NS)

    try:
        # S314: the sitemap is a trusted build artifact produced by our
        # own zensical build step seconds earlier, not untrusted input.
        tree = ET.parse(SITEMAP_FILE)  # noqa: S314
    except ET.ParseError as exc:
        print(f"Failed to parse sitemap: {exc}", file=sys.stderr)
        return 1

    root = tree.getroot()
    existing = {
        loc.text for loc in root.findall(f"{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc")
    }

    added = 0
    for url in EXTRA_URLS:
        if url in existing:
            print(f"  skip (already present): {url}")
            continue
        url_elem = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        loc_elem = ET.SubElement(url_elem, f"{{{SITEMAP_NS}}}loc")
        loc_elem.text = url
        added += 1
        print(f"  added: {url}")

    if added == 0:
        print("Sitemap already contains all extra URLs; no changes written.")
        return 0

    # ET.indent keeps the file diff-friendly if it ever needs a human read.
    ET.indent(tree, space="  ")
    tree.write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {added} extra URL(s) to {SITEMAP_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
