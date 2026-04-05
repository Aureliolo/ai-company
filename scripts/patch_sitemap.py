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

import defusedxml.ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

REPO_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_FILE = REPO_ROOT / "_site" / "docs" / "sitemap.xml"

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
URLSET_TAG = f"{{{SITEMAP_NS}}}urlset"
URL_TAG = f"{{{SITEMAP_NS}}}url"
LOC_TAG = f"{{{SITEMAP_NS}}}loc"

# Static artifacts that should be discoverable but live outside the
# Markdown-driven nav tree. Paths are relative to the docs root URL,
# which is derived at runtime from the existing sitemap entries so the
# script stays in sync with whatever `site_url` mkdocs.yml resolves to
# (production, staging, PR previews).
EXTRA_PATHS: tuple[str, ...] = (
    "openapi/reference.html",
    "openapi/openapi.json",
)


def main() -> int:  # noqa: PLR0911 -- one return per distinct failure mode
    """Patch the built sitemap to include the static OpenAPI artifact URLs.

    Idempotent: on rerun (when all URLs are already present) the file is
    not rewritten. Returns 1 if the sitemap file is missing, malformed,
    has an unexpected root element, has no entries to derive a base URL
    from, or cannot be written back; 0 otherwise.
    """
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

    # Register the default namespace so ElementTree serialises tags as
    # `<url>` rather than `<ns0:url>`. Must be called before tree.write(),
    # not before parse -- parse is unaffected by the registry.
    ET.register_namespace("", SITEMAP_NS)

    try:
        # defusedxml guards against billion-laughs, XXE, and DTD abuse.
        # The sitemap is produced by our own zensical build step, but
        # using the hardened parser costs nothing and removes the
        # supply-chain assumption from the code.
        tree = DefusedET.parse(SITEMAP_FILE)
    except (ET.ParseError, DefusedXmlException) as exc:
        print(
            f"Failed to parse sitemap at {SITEMAP_FILE.relative_to(REPO_ROOT)}: {exc}",
            file=sys.stderr,
        )
        return 1

    root = tree.getroot()
    if root is None or root.tag != URLSET_TAG:
        actual = "<empty tree>" if root is None else repr(root.tag)
        print(
            f"Error: sitemap root element is {actual}, expected {URLSET_TAG!r}.",
            file=sys.stderr,
        )
        print(
            "The sitemap may use a different schema version or be a "
            "sitemap index; update patch_sitemap.py to match.",
            file=sys.stderr,
        )
        return 1

    existing: set[str] = {
        (loc.text or "").strip() for loc in root.findall(f"{URL_TAG}/{LOC_TAG}")
    }
    existing.discard("")

    if not existing:
        print(
            "Error: sitemap has no <url> entries; cannot derive base URL.",
            file=sys.stderr,
        )
        return 1

    # The shortest existing URL is the docs root (index.md always maps
    # to the shortest path in a mkdocs-generated sitemap). Stripping the
    # trailing slash gives us a base we can concatenate paths onto.
    base_url = min(existing, key=len).rstrip("/")

    added = 0
    for path in EXTRA_PATHS:
        url = f"{base_url}/{path}"
        if url in existing:
            print(f"  skip (already present): {url}")
            continue
        url_elem = ET.SubElement(root, URL_TAG)
        loc_elem = ET.SubElement(url_elem, LOC_TAG)
        loc_elem.text = url
        added += 1
        print(f"  added: {url}")

    if added == 0:
        print("Sitemap already contains all extra URLs; no changes written.")
        return 0

    # ET.indent keeps the file diff-friendly if it ever needs a human read.
    ET.indent(tree, space="  ")
    try:
        tree.write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        print(
            f"Failed to write patched sitemap to "
            f"{SITEMAP_FILE.relative_to(REPO_ROOT)}: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"Wrote {added} extra URL(s) to {SITEMAP_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
