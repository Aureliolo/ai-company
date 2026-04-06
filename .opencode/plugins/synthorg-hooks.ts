/**
 * SynthOrg hooks plugin for OpenCode.
 *
 * Mirrors the Claude Code hooks defined in .claude/settings.json and
 * .claude/settings.local.json by calling the same shell scripts.
 *
 * Committed Claude Code hooks (from .claude/settings.json):
 *   PreToolUse (Bash): scripts/check_push_rebased.sh
 *
 * Hookify rules enforced via this plugin (from .claude/hookify.*.md):
 *   block-pr-create: blocks direct `gh pr create`
 *   enforce-parallel-tests: enforces `-n 8` with pytest
 *   no-cd-prefix: blocks `cd` prefix in Bash commands
 *   no-local-coverage: blocks `--cov` flags locally
 *   check_bash_no_write.sh: blocks file writes via Bash
 *   check_git_c_cwd.sh: blocks unnecessary git -C to cwd
 *   check_web_design_system.py: validates design tokens on web file edits
 */

import type { Plugin } from "@opencode-ai/plugin";
import { spawnSync, execSync } from "child_process";

function runHookScript(
  scriptPath: string,
  toolInput: Record<string, unknown>,
  timeoutMs: number = 10000,
): string | null {
  try {
    const input = JSON.stringify({ tool_input: toolInput });
    const result = spawnSync("bash", [scriptPath], {
      input,
      timeout: timeoutMs,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    if (result.status === 2) {
      // Hook denied the action
      return result.stdout ?? "Hook denied this action";
    }
    if (result.status !== 0) {
      // Fail closed: non-zero, non-2 exit codes are errors
      return null;
    }
    return result.stdout;
  } catch (error: unknown) {
    const err = error as { status?: number; stdout?: string };
    if (err.status === 2) {
      // Hook denied the action
      return err.stdout ?? "Hook denied this action";
    }
    // Fail closed on catch errors too
    return null;
  }
}

export const SynthOrgHooks: Plugin = async ({ client, $, app }) => {
  return {
    tool: {
      execute: {
        before: async (input, output) => {
          // Only intercept Bash/shell tool calls
          if (input.tool === "bash" || input.tool === "shell") {
            const command = (output.args?.command as string) ?? "";

            // block-pr-create: block direct gh pr create
            if (/gh\s+pr\s+create/i.test(command)) {
              throw new Error(
                "PR creation blocked. Use `/pre-pr-review` instead -- it runs automated checks + review agents + fixes before creating the PR. For trivial or docs-only changes: `/pre-pr-review quick` skips agents but still runs automated checks.",
              );
            }

            // enforce-parallel-tests: enforce -n 8 with pytest
            if (
              /(?:^|\s)(?:pytest|run\s+pytest|python\s+-m\s+pytest)\b/i.test(command) &&
              !/-n 8/.test(command)
            ) {
              throw new Error(
                "Always use `-n 8` with pytest for parallel execution. Add `-n 8` to your pytest command. Never run tests sequentially or with `-n auto` (32 workers causes crashes and is slower due to contention).",
              );
            }

            // no-cd-prefix: block cd prefix in Bash commands (with optional leading whitespace)
            if (/^\s*cd\s+/i.test(command)) {
              throw new Error(
                "BLOCKED: Do not use `cd` in Bash commands -- it poisons the cwd for all subsequent calls. The working directory is ALREADY set to the project root. Run commands directly. For Go commands: use `go -C cli <command>`. For subdir tools without a `-C`/`--prefix` equivalent: use `bash -c \"cd <dir> && <cmd>\"`.",
              );
            }

            // no-local-coverage: block --cov flags locally
            if (
              /(?:^|\s)(?:pytest|run\s+pytest|python\s+-m\s+pytest)\b/i.test(command) &&
              /--cov\b/.test(command)
            ) {
              throw new Error(
                "Do not run pytest with coverage locally -- CI handles it. Coverage adds 20-40% overhead. Remove `--cov`, `--cov-report`, and `--cov-fail-under` from your command.",
              );
            }

            // check_push_rebased.sh -- block push if branch is behind main
            if (command.includes("git push")) {
              const result = runHookScript(
                "scripts/check_push_rebased.sh",
                { command },
                15000,
              );
              if (result) {
                try {
                  const parsed = JSON.parse(result);
                  if (parsed.hookSpecificOutput?.permissionDecision === "deny") {
                    throw new Error(parsed.hookSpecificOutput?.permissionDecisionReason || "Push blocked");
                  }
                } catch {
                  // Not JSON or parse error - check for legacy "block" pattern
                  if (result.includes("block")) {
                    throw new Error(result);
                  }
                }
              }
            }

            // check_bash_no_write.sh -- block file writes via Bash
            const result = runHookScript(
              "scripts/check_bash_no_write.sh",
              { command },
              5000,
            );
            if (result && result.includes("deny")) {
              throw new Error(result);
            }

            // check_git_c_cwd.sh -- block unnecessary git -C to cwd
            if (command.includes("git") && command.includes("-C")) {
              const gitResult = runHookScript(
                "scripts/check_git_c_cwd.sh",
                { command },
                5000,
              );
              if (gitResult && gitResult.includes("deny")) {
                throw new Error(gitResult);
              }
            }
          }
        },
        after: async (input, output) => {
          // check_web_design_system.py -- validate design tokens on web file edits
          if (
            (input.tool === "edit" || input.tool === "write") &&
            typeof output.args?.file_path === "string" &&
            output.args.file_path.includes("web/src/")
          ) {
            try {
              execSync(
                `python scripts/check_web_design_system.py`,
                { timeout: 10000, encoding: "utf-8" },
              );
            } catch (error: unknown) {
              const err = error as { message?: string; stderr?: string };
              const errMsg = err.message || err.stderr || "Unknown error";
              throw new Error(`Design system check failed for ${output.args.file_path}: ${errMsg}`);
            }
          }
        },
      },
    },
  };
};

export default SynthOrgHooks;
