#!/usr/bin/env python3
"""Issue Analyzer for SynthOrg.

Analyzes GitHub issues for priority/scope reorganization.
Usage: python scripts/issue_analyzer.py [command] [args]

Commands:
  analyze     - Full analysis of open issues
  summary     - Brief summary by version
  critical    - Show only critical/high issues
  propose     - Propose new labels/versions
  deps        - Show dependency chains
"""

import json
import re
import subprocess
import sys
from collections import defaultdict

# Constants
ZAP_REPORT_ISSUE_NUMBER = 760
ACCEPTANCE_CRITERIA_THRESHOLD = 10
MAX_DISPLAY_ISSUES = 12
MIN_CLI_ARGS = 2

# Issue analyzer for SynthOrg - no external dependencies needed


def run_gh_issue_list(limit: int = 200, state: str = "open") -> list[dict]:
    """Fetch issues from GitHub CLI.

    Args:
        limit: Maximum number of issues to fetch.
        state: Issue state filter ("open", "closed", "all").

    Returns:
        List of issue dictionaries from GitHub API.

    Raises:
        SystemExit: If the gh CLI is not installed or the API call fails.
    """
    cmd = [
        "gh",
        "issue",
        "list",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,labels,body,createdAt,updatedAt",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return json.loads(result.stdout)
    except FileNotFoundError:
        print(
            "Error: 'gh' CLI not found. Please install GitHub CLI: https://cli.github.com",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issues: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)


def get_label_value(labels: list[dict], prefix: str) -> str:
    """Extract label value by prefix.

    Args:
        labels: List of label dictionaries from GitHub API.
        prefix: Label prefix to search for (e.g., "scope", "prio").

    Returns:
        The label value after the prefix, or "unknown" if not found.
    """
    for label in labels:
        name = label["name"]
        if name.startswith(prefix + ":"):
            return name.split(":", 1)[1]
    return "unknown"


def analyze_scope(body: str, title: str) -> dict[str, bool | int]:
    """Analyze technical scope from issue body.

    Args:
        body: Issue body text.
        title: Issue title (for future analysis use).

    Returns:
        Dictionary with scope analysis flags and acceptance criteria count.
    """
    body_lower = body.lower()
    _ = title  # title may be used for future analysis
    return {
        "has_endpoints": "endpoint" in body_lower,
        "has_tests": "test" in body_lower
        and any(x in body_lower for x in ["unit test", "integration test"]),
        "has_ws": "websocket" in body_lower or "ws " in body_lower,
        "has_ui": any(x in body_lower for x in ["ui", "frontend", "dashboard"]),
        "has_auth": any(
            x in body_lower for x in ["auth", "permission", "role", "session"]
        ),
        "has_complex_logic": any(
            x in body_lower
            for x in [
                "algorithm",
                "pipeline",
                "orchestration",
                "consensus",
                "distributed",
            ]
        ),
        "has_db": "database" in body_lower or "persistence" in body_lower,
        "ac_count": body.count("- [ ]"),
    }


def categorize_issue(issue: dict) -> dict[str, str | int | list[str]]:
    """Categorize an issue by priority and scope.

    Args:
        issue: Issue dictionary from GitHub API.

    Returns:
        Dictionary with original and recommended priority/scope,
        along with analysis metadata.
    """
    num = issue["number"]
    title = issue["title"]
    labels = issue.get("labels", [])
    body = issue.get("body", "") or ""

    current_scope = get_label_value(labels, "scope")
    current_prio = get_label_value(labels, "prio")
    issue_type = get_label_value(labels, "type")
    versions = [label["name"] for label in labels if label["name"].startswith("v0.")]

    analysis = analyze_scope(body, title)

    # Re-assess priority based on actual product value
    recommended_prio = current_prio
    recommended_scope = current_scope
    reason = ""

    # CRITICAL: Core editing is broken
    if num in [1081, 1082]:
        recommended_prio = "critical"
        recommended_scope = "medium"
        reason = "Blocking core functionality - dashboard editing doesn't work"

    # HIGH: Quick wins with major value
    elif num in [1080, 1079, 1077]:
        recommended_prio = "high"
        recommended_scope = "small"
        reason = "Fast implementation, high user value"

    # Research items - deferrable
    elif issue_type == "research":
        recommended_prio = "low"
        reason = "Needs evaluation before implementation"

    # Speculative features - future
    elif num in [251, 252, 253, 254, 255, 242, 241, 250, 249, 248, 246, 1012, 1005]:
        recommended_prio = "low"
        reason = "Aspirational features - revisit later"

    # Scope re-assessments
    if current_scope == "large":
        if analysis["ac_count"] == 0 and not analysis["has_complex_logic"]:
            recommended_scope = "medium"
            scope_reason = "No complex logic or acceptance criteria - likely medium"
            reason = f"{reason}; {scope_reason}" if reason else scope_reason
        elif (
            analysis["has_endpoints"]
            and analysis["ac_count"] < ACCEPTANCE_CRITERIA_THRESHOLD
        ):
            recommended_scope = "medium"
            scope_reason = "Standard CRUD endpoints, not complex architecture"
            reason = f"{reason}; {scope_reason}" if reason else scope_reason

    return {
        "num": num,
        "title": title,
        "current_prio": current_prio,
        "current_scope": current_scope,
        "recommended_prio": recommended_prio,
        "recommended_scope": recommended_scope,
        "versions": versions,
        "issue_type": issue_type,
        "reason": reason,
        **analysis,
    }


def _format_issue_tags(issue: dict) -> str:
    """Format issue attributes as tags string."""
    attrs = []
    if issue["has_endpoints"]:
        attrs.append("endpoints")
    if issue["has_ui"]:
        attrs.append("UI")
    if issue["has_auth"]:
        attrs.append("auth")
    if issue["has_complex_logic"]:
        attrs.append("complex")
    if issue["ac_count"] > 0:
        attrs.append(f"{issue['ac_count']} AC")
    return ", ".join(attrs) if attrs else ""


def _print_issue_details(issue: dict) -> None:
    """Print details for a single issue."""
    print(f"\n  #{issue['num']}: {issue['title'][:60]}")
    print(
        f"    Current: {issue['current_prio']}/{issue['current_scope']} -> "
        f"Recommended: {issue['recommended_prio']}/{issue['recommended_scope']}"
    )
    if issue["reason"]:
        print(f"    Reason: {issue['reason'][:80]}")
    if issue["versions"]:
        print(f"    Versions: {', '.join(issue['versions'])}")
    tags = _format_issue_tags(issue)
    if tags:
        print(f"    Tags: {tags}")


def print_full_analysis(issues: list[dict]) -> None:
    """Print detailed analysis of all issues grouped by priority.

    Args:
        issues: List of issue dictionaries from GitHub API.
    """
    categorized = [
        categorize_issue(i) for i in issues if i["number"] != ZAP_REPORT_ISSUE_NUMBER
    ]  # Skip ZAP report

    print("=" * 80)
    print("SYNTHORG ISSUE ANALYZER")
    print("=" * 80)
    print()

    # Group by recommended priority
    groups: dict[str, list[dict]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
        "unknown": [],
    }

    for c in categorized:
        prio = c["recommended_prio"]
        if prio not in groups:
            prio = "unknown"
        groups[prio].append(c)

    # Print groups
    for prio in ["critical", "high", "medium", "low", "unknown"]:
        prio_issues = groups[prio]
        if not prio_issues:
            continue

        print(f"\n{'=' * 40}")
        print(f"PRIORITY: {prio.upper()} ({len(prio_issues)} issues)")
        print(f"{'=' * 40}")

        for issue in sorted(prio_issues, key=lambda x: (-x["ac_count"], x["num"])):
            _print_issue_details(issue)


def print_summary(issues: list[dict]) -> None:
    """Print brief summary by version.

    Args:
        issues: List of issue dictionaries from GitHub API.
    """
    version_counts = defaultdict(
        lambda: {"total": 0, "high": 0, "medium": 0, "low": 0, "unscoped": 0}
    )

    for issue in issues:
        if issue["number"] == ZAP_REPORT_ISSUE_NUMBER:
            continue

        labels = issue.get("labels", [])
        versions = [
            label["name"] for label in labels if label["name"].startswith("v0.")
        ]
        prio = get_label_value(labels, "prio")

        if not versions:
            version_counts["NO_VERSION"]["total"] += 1
            version_counts["NO_VERSION"][
                prio if prio in ["high", "medium", "low"] else "unscoped"
            ] += 1
        else:
            for v in versions:
                version_counts[v]["total"] += 1
                version_counts[v][
                    prio if prio in ["high", "medium", "low"] else "unscoped"
                ] += 1

    print("\n" + "=" * 60)
    print("ISSUE COUNT BY VERSION")
    print("=" * 60)
    print(f"{'Version':<12} {'Total':>6} {'High':>6} {'Medium':>6} {'Low':>6}")
    print("-" * 60)

    for version in sorted(version_counts.keys()):
        counts = version_counts[version]
        print(
            f"{version:<12} {counts['total']:>6} {counts['high']:>6} {counts['medium']:>6} {counts['low']:>6}"
        )


def print_critical(issues: list[dict]) -> None:
    """Print only critical/high priority issues.

    Args:
        issues: List of issue dictionaries from GitHub API.
    """
    categorized = [
        categorize_issue(i) for i in issues if i["number"] != ZAP_REPORT_ISSUE_NUMBER
    ]
    critical = [c for c in categorized if c["recommended_prio"] in ["critical", "high"]]

    print("\n" + "=" * 60)
    print("CRITICAL & HIGH PRIORITY ISSUES")
    print("=" * 60)

    for issue in sorted(
        critical, key=lambda x: (x["recommended_prio"] != "critical", x["num"])
    ):
        print(f"\n#{issue['num']}: {issue['title']}")
        print(f"  Priority: {issue['recommended_prio'].upper()}")
        print(f"  Scope: {issue['current_scope']} -> {issue['recommended_scope']}")
        if issue["reason"]:
            print(f"  Why: {issue['reason']}")


def find_dependencies(issues: list[dict]) -> list[tuple[int, int]]:
    """Find dependency chains in issue bodies.

    Args:
        issues: List of issue dictionaries from GitHub API.

    Returns:
        List of (source_issue, target_issue) dependency tuples.
    """
    deps = []

    for issue in issues:
        body = issue.get("body", "") or ""

        # Common dependency patterns
        patterns = [
            r"(?:depends?\s+(?:on|upon)|blocked\s+(?:by|on)|requires?|needs?|builds?\s+on)\s*[:\s]*#(\d+)",
            r"(?:follow(?:s|ing|[- ]up)|extends?)\s*[:\s]*#(\d+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            deps.extend((issue["number"], int(m)) for m in matches)

    print("\n" + "=" * 60)
    print("DEPENDENCY CHAINS")
    print("=" * 60)

    if deps:
        for src, dst in sorted(set(deps)):
            print(f"  #{src} -> depends on -> #{dst}")
    else:
        print("  No explicit dependencies found")

    return deps


def propose_reorganization(issues: list[dict]) -> None:
    """Propose new version organization based on priority analysis.

    Args:
        issues: List of issue dictionaries from GitHub API.
    """
    categorized = [
        categorize_issue(i) for i in issues if i["number"] != ZAP_REPORT_ISSUE_NUMBER
    ]

    print("\n" + "=" * 60)
    print("PROPOSED REORGANIZATION")
    print("=" * 60)

    # Define version buckets based on recommended priority
    v064 = []  # Critical
    v065 = []  # High
    v070 = []  # Medium
    v080 = []  # Low + research

    for c in categorized:
        if c["recommended_prio"] == "critical":
            v064.append(c)
        elif c["recommended_prio"] == "high":
            v065.append(c)
        elif c["recommended_prio"] == "medium":
            v070.append(c)
        else:
            v080.append(c)

    print(f"\n### v0.6.4 (CRITICAL - {len(v064)} issue{'s' if len(v064) != 1 else ''})")
    print("Theme: Foundation - dashboard editing actually works\n")
    for c in sorted(v064, key=lambda x: x["num"]):
        print(f"  #{c['num']}: {c['title'][:55]} [{c['recommended_scope']}]")

    print(f"\n### v0.6.5 (HIGH PRIORITY - {len(v065)} issues)")
    print("Theme: User value - polish and features\n")
    for c in sorted(v065, key=lambda x: (x["has_ui"], x["num"]), reverse=True)[
        :MAX_DISPLAY_ISSUES
    ]:
        print(f"  #{c['num']}: {c['title'][:55]} [{c['recommended_scope']}]")
    if len(v065) > MAX_DISPLAY_ISSUES:
        print(f"  ... and {len(v065) - MAX_DISPLAY_ISSUES} more")

    print(f"\n### v0.7.0 (MEDIUM - {len(v070)} issues)")
    print("Theme: Engine hardening\n")
    for c in sorted(v070, key=lambda x: x["num"])[:8]:
        print(f"  #{c['num']}: {c['title'][:55]} [{c['recommended_scope']}]")

    print(f"\n### v0.8.x / Future ({len(v080)} issues)")
    print("Theme: Research and aspirational features")


def main() -> None:
    """Main entry point for the issue analyzer."""
    if len(sys.argv) < MIN_CLI_ARGS:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    # Validate command before fetching issues (fail fast)
    valid_commands = {"analyze", "summary", "critical", "deps", "propose"}
    if command not in valid_commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    # Fetch issues
    print("Fetching issues from GitHub...", file=sys.stderr)
    issues = run_gh_issue_list()
    print(f"Found {len(issues)} open issues\n", file=sys.stderr)

    if command == "analyze":
        print_full_analysis(issues)
    elif command == "summary":
        print_summary(issues)
    elif command == "critical":
        print_critical(issues)
    elif command == "deps":
        find_dependencies(issues)
    elif command == "propose":
        propose_reorganization(issues)


if __name__ == "__main__":
    main()
