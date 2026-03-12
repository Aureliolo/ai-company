"""Export the Litestar OpenAPI schema to a static JSON file.

Used by CI (pages.yml, pages-preview.yml) to generate
``docs/_generated/openapi.json`` before the MkDocs build, so the
Scalar-based REST API reference page can load the schema statically.
"""

import json
import sys
from pathlib import Path

# Repository root is the parent of the scripts/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "_generated"
OUTPUT_FILE = OUTPUT_DIR / "openapi.json"


def main() -> None:
    """Instantiate the app, extract the OpenAPI schema, and write JSON."""
    from ai_company.api.app import create_app

    app = create_app()
    schema_dict = app.openapi_schema.to_schema()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI schema to {OUTPUT_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    sys.exit(main() or 0)
