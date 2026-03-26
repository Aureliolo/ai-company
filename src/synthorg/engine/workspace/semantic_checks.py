"""AST-based semantic conflict checks for Python files.

Pure functions that take parsed source maps and return detected
conflicts. Each function handles one category of semantic conflict.
Files with syntax errors are silently skipped (logged at DEBUG).
"""

import ast
from collections import Counter

from synthorg.core.enums import ConflictType
from synthorg.engine.workspace.models import MergeConflict
from synthorg.observability import get_logger

logger = get_logger(__name__)


def _safe_parse(source: str, filename: str) -> ast.Module | None:
    """Parse source code, returning None on syntax errors."""
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError:
        logger.debug(
            "semantic.check.parse_skip",
            file=filename,
            reason="syntax_error",
        )
        return None


def _top_level_names(tree: ast.Module) -> dict[str, ast.stmt]:
    """Extract top-level function, class, and assignment names.

    Returns:
        Mapping from name to the AST node that defines it.
    """
    names: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(
            node,
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        ):
            names[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id] = node
    return names


def _all_name_references(tree: ast.Module) -> set[str]:
    """Collect all Name nodes referenced in the module."""
    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.add(node.id)
    return refs


def _function_min_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the minimum number of positional arguments a function requires.

    Excludes self/cls for methods, counts only required args
    (those without defaults).
    """
    args = node.args
    return len(args.args) - len(args.defaults)


def _function_max_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the maximum number of positional arguments a function accepts.

    Returns a large number if *args is present.
    """
    if node.args.vararg is not None:
        return 999
    return len(node.args.args)


def _function_param_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return all parameter names accepted by a function."""
    names: set[str] = set()
    for arg in node.args.args:
        names.add(arg.arg)
    for arg in node.args.posonlyargs:
        names.add(arg.arg)
    for arg in node.args.kwonlyargs:
        names.add(arg.arg)
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _call_keyword_names(call: ast.Call) -> set[str]:
    """Return keyword argument names used in a call."""
    return {kw.arg for kw in call.keywords if kw.arg is not None}


def _find_calls_to(tree: ast.Module, name: str) -> list[ast.Call]:
    """Find all direct calls to a named function in the AST."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def _imported_names(tree: ast.Module) -> list[tuple[str, str, str]]:
    """Extract from-import names: (module, imported_name, alias).

    Only handles ``from X import Y`` style imports.
    Star imports are excluded.
    """
    result: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                result.append(
                    (node.module, alias.name, alias.asname or alias.name),
                )
    return result


# ---------------------------------------------------------------------------
# Public check functions
# ---------------------------------------------------------------------------


def _collect_removed_names(
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> dict[str, str]:
    """Find top-level names removed between base and merged.

    Returns:
        Mapping from removed name to source file path.
    """
    removed: dict[str, str] = {}
    for file_path, base_src in base_sources.items():
        merged_src = merged_sources.get(file_path)
        if merged_src is None:
            continue
        base_tree = _safe_parse(base_src, file_path)
        merged_tree = _safe_parse(merged_src, file_path)
        if base_tree is None or merged_tree is None:
            continue
        base_names = set(_top_level_names(base_tree))
        merged_names = set(_top_level_names(merged_tree))
        for name in base_names - merged_names:
            removed[name] = file_path
    return removed


def check_removed_references(
    *,
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> tuple[MergeConflict, ...]:
    """Detect references to names removed by the merge.

    Compares top-level definitions in base vs merged sources to find
    names that were removed, then checks if those names are still
    referenced in any merged file.

    Args:
        base_sources: File path to source code before merge.
        merged_sources: File path to source code after merge.

    Returns:
        Tuple of semantic conflicts for removed-name references.
    """
    if not base_sources or not merged_sources:
        return ()

    removed_names = _collect_removed_names(base_sources, merged_sources)
    if not removed_names:
        return ()

    conflicts: list[MergeConflict] = []
    for file_path, merged_src in merged_sources.items():
        merged_tree = _safe_parse(merged_src, file_path)
        if merged_tree is None:
            continue
        refs = _all_name_references(merged_tree)
        for name, source_file in removed_names.items():
            if file_path != source_file and name in refs:
                conflicts.append(
                    MergeConflict(
                        file_path=file_path,
                        conflict_type=ConflictType.SEMANTIC,
                        description=(
                            f"References '{name}' which was removed "
                            f"from '{source_file}' during merge"
                        ),
                    ),
                )
    return tuple(conflicts)


_SigInfo = tuple[int, int, int, int, set[str]]


def _collect_changed_sigs(
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> dict[str, _SigInfo]:
    """Find functions whose signatures changed between base and merged.

    Returns:
        Mapping from function name to
        (old_min, old_max, new_min, new_max, new_param_names).
    """
    changed: dict[str, _SigInfo] = {}
    for file_path, base_src in base_sources.items():
        merged_src = merged_sources.get(file_path)
        if merged_src is None:
            continue
        base_tree = _safe_parse(base_src, file_path)
        merged_tree = _safe_parse(merged_src, file_path)
        if base_tree is None or merged_tree is None:
            continue
        _compare_signatures(
            _top_level_names(base_tree),
            _top_level_names(merged_tree),
            changed,
        )
    return changed


def _compare_signatures(
    base_names: dict[str, ast.stmt],
    merged_names: dict[str, ast.stmt],
    out: dict[str, _SigInfo],
) -> None:
    """Compare function signatures and record changes in *out*."""
    func_types = ast.FunctionDef | ast.AsyncFunctionDef
    for name, base_node in base_names.items():
        merged_node = merged_names.get(name)
        if merged_node is None:
            continue
        if not isinstance(base_node, func_types):
            continue
        if not isinstance(merged_node, func_types):
            continue

        old_min = _function_min_args(base_node)
        old_max = _function_max_args(base_node)
        new_min = _function_min_args(merged_node)
        new_max = _function_max_args(merged_node)
        new_params = _function_param_names(merged_node)
        old_params = _function_param_names(base_node)
        has_kwargs = merged_node.args.kwarg is not None

        if old_min != new_min or old_max != new_max or old_params - new_params:
            out[name] = (
                old_min,
                old_max,
                new_min,
                new_max,
                new_params if not has_kwargs else set(),
            )


def _check_call_compat(
    file_path: str,
    name: str,
    call: ast.Call,
    sig: _SigInfo,
) -> MergeConflict | None:
    """Check a single call against the new signature."""
    _, _, new_min, new_max, new_params = sig
    pos_count = len(call.args)
    if pos_count < new_min or pos_count > new_max:
        return MergeConflict(
            file_path=file_path,
            conflict_type=ConflictType.SEMANTIC,
            description=(
                f"Calls '{name}' with {pos_count} positional "
                f"argument(s) but merged signature "
                f"requires {new_min}-{new_max}"
            ),
        )
    if new_params:
        invalid_kws = _call_keyword_names(call) - new_params
        if invalid_kws:
            return MergeConflict(
                file_path=file_path,
                conflict_type=ConflictType.SEMANTIC,
                description=(
                    f"Calls '{name}' with keyword argument(s) "
                    f"{sorted(invalid_kws)} removed from merged "
                    f"signature"
                ),
            )
    return None


def check_signature_changes(
    *,
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> tuple[MergeConflict, ...]:
    """Detect function signature changes that may break callers.

    Finds functions whose required parameter count changed between
    base and merged, then checks if callers in other merged files
    still pass the old number of arguments.

    Args:
        base_sources: File path to source code before merge.
        merged_sources: File path to source code after merge.

    Returns:
        Tuple of semantic conflicts for signature incompatibilities.
    """
    if not base_sources or not merged_sources:
        return ()

    changed_sigs = _collect_changed_sigs(base_sources, merged_sources)
    if not changed_sigs:
        return ()

    conflicts: list[MergeConflict] = []
    for file_path, merged_src in merged_sources.items():
        merged_tree = _safe_parse(merged_src, file_path)
        if merged_tree is None:
            continue
        for name, sig in changed_sigs.items():
            for call in _find_calls_to(merged_tree, name):
                conflict = _check_call_compat(
                    file_path,
                    name,
                    call,
                    sig,
                )
                if conflict is not None:
                    conflicts.append(conflict)
    return tuple(conflicts)


def check_duplicate_definitions(
    *,
    merged_sources: dict[str, str],
) -> tuple[MergeConflict, ...]:
    """Detect duplicate top-level function or class definitions.

    Two branches may independently define the same name at module
    level. After merge, the later definition silently shadows the
    earlier one.

    Args:
        merged_sources: File path to source code after merge.

    Returns:
        Tuple of semantic conflicts for duplicate definitions.
    """
    if not merged_sources:
        return ()

    conflicts: list[MergeConflict] = []
    for file_path, source in merged_sources.items():
        tree = _safe_parse(source, file_path)
        if tree is None:
            continue

        name_counts: Counter[str] = Counter()
        for node in tree.body:
            if isinstance(
                node,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
            ):
                name_counts[node.name] += 1

        for name, count in name_counts.items():
            if count > 1:
                conflicts.append(
                    MergeConflict(
                        file_path=file_path,
                        conflict_type=ConflictType.SEMANTIC,
                        description=(
                            f"Duplicate top-level definition '{name}' "
                            f"appears {count} times"
                        ),
                    ),
                )
    return tuple(conflicts)


def _collect_removed_exports(
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> dict[str, set[str]]:
    """Find module-level names removed between base and merged.

    Returns:
        Mapping from module stem to set of removed export names.
    """
    removed: dict[str, set[str]] = {}
    for file_path, base_src in base_sources.items():
        merged_src = merged_sources.get(file_path)
        if merged_src is None:
            continue
        base_tree = _safe_parse(base_src, file_path)
        merged_tree = _safe_parse(merged_src, file_path)
        if base_tree is None or merged_tree is None:
            continue
        gone = set(_top_level_names(base_tree)) - set(
            _top_level_names(merged_tree),
        )
        if gone:
            module_stem = file_path.removesuffix(".py").replace("/", ".")
            removed[module_stem] = gone
    return removed


def check_import_conflicts(
    *,
    base_sources: dict[str, str],
    merged_sources: dict[str, str],
) -> tuple[MergeConflict, ...]:
    """Detect imports of names that were removed from their source module.

    When one branch removes a name from a module and another branch
    adds an import of that name, the import will fail at runtime.

    Args:
        base_sources: File path to source code before merge.
        merged_sources: File path to source code after merge.

    Returns:
        Tuple of semantic conflicts for broken imports.
    """
    if not base_sources or not merged_sources:
        return ()

    removed_exports = _collect_removed_exports(base_sources, merged_sources)
    if not removed_exports:
        return ()

    conflicts: list[MergeConflict] = []
    for file_path, merged_src in merged_sources.items():
        merged_tree = _safe_parse(merged_src, file_path)
        if merged_tree is None:
            continue
        for module, name, _ in _imported_names(merged_tree):
            if name in removed_exports.get(module, set()):
                conflicts.append(
                    MergeConflict(
                        file_path=file_path,
                        conflict_type=ConflictType.SEMANTIC,
                        description=(
                            f"Imports '{name}' from '{module}' but "
                            f"'{name}' was removed during merge"
                        ),
                    ),
                )
    return tuple(conflicts)
