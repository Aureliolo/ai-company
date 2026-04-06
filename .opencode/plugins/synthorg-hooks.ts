/**
 * SynthOrg hooks plugin for OpenCode.
 *
 * Mirrors the Claude Code hooks defined in .claude/settings.json and
 * .claude/settings.local.json by calling the same shell scripts.
 *
 * Claude Code hooks:
 *   PreToolUse (Bash): scripts/check_push_rebased.sh
 *   PreToolUse (Bash): scripts/check_bash_no_write.sh
 *   PreToolUse (Bash): scripts/check_git_c_cwd.sh
 *   PostToolUse (Edit|Write): scripts/check_web_design_system.py
 */

import type { Plugin } from "@opencode-ai/plugin";
import { execSync } from "child_process";

function runHookScript(
  scriptPath: string,
  toolInput: Record<string, unknown>,
  timeoutMs: number = 10000,
): string | null {
  try {
    const input = JSON.stringify({ tool_input: toolInput });
    const result = execSync(`echo '${input.replace(/'/g, "\\'")}' | bash ${scriptPath}`, {
      timeout: timeoutMs,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    return result;
  } catch (error: unknown) {
    const err = error as { status?: number; stdout?: string };
    if (err.status === 2) {
      // Hook denied the action
      return err.stdout ?? "Hook denied this action";
    }
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

            // check_push_rebased.sh -- block push if branch is behind main
            if (command.includes("git push")) {
              const result = runHookScript(
                "scripts/check_push_rebased.sh",
                { command },
                15000,
              );
              if (result && result.includes("block")) {
                throw new Error(result);
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
              if (gitResult && gitResult.includes("block")) {
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
            } catch {
              // Log but don't block -- PostToolUse is advisory
              console.error("Design system check failed for:", output.args.file_path);
            }
          }
        },
      },
    },
  };
};

export default SynthOrgHooks;
