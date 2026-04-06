/**
 * Memory persistence plugin for OpenCode.
 *
 * Provides read/write access to the shared MEMORY.md system used by
 * both Claude Code and OpenCode. Memory files live in:
 *   ~/.claude/projects/<mangled-cwd>/memory/
 *
 * Format (same as Claude Code):
 *   - MEMORY.md: index file with one-line pointers
 *   - Individual .md files with frontmatter (name, description, type)
 *   - Types: user, feedback, project, reference
 */

import type { Plugin } from "@opencode-ai/plugin";
import { existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from "fs";
import { join, resolve, dirname } from "path";
import { homedir } from "os";

function getMemoryDir(): string {
  const cwd = process.cwd();
  const mangled = cwd.replace(/[:/\\]/g, "_").replace(/^_/, "").replace(/_$/, "");
  return join(homedir(), ".claude", "projects", mangled, "memory");
}

const MEMORY_DIR = getMemoryDir();
const MEMORY_INDEX = join(MEMORY_DIR, "MEMORY.md");

interface MemoryEntry {
  name: string;
  description: string;
  type: "user" | "feedback" | "project" | "reference";
  content: string;
}

function ensureMemoryDir(): void {
  if (!existsSync(MEMORY_DIR)) {
    mkdirSync(MEMORY_DIR, { recursive: true });
  }
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function buildFrontmatter(entry: MemoryEntry): string {
  return [
    "---",
    `name: ${entry.name}`,
    `description: ${entry.description}`,
    `type: ${entry.type}`,
    "---",
    "",
    entry.content,
    "",
  ].join("\n");
}

function updateIndex(action: "add" | "remove", filename: string, title: string, hook: string): void {
  ensureMemoryDir();
  let index = "";
  if (existsSync(MEMORY_INDEX)) {
    index = readFileSync(MEMORY_INDEX, "utf-8");
  } else {
    index = "# SynthOrg Project Memory\n\n";
  }

  if (action === "add") {
    const entry = `- [${title}](${filename}) -- ${hook}`;
    if (!index.includes(filename)) {
      index = index.trimEnd() + "\n" + entry + "\n";
    }
  } else if (action === "remove") {
    const lines = index.split("\n").filter((line) => !line.includes(filename));
    index = lines.join("\n") + "\n";
  }

  writeFileSync(MEMORY_INDEX, index, "utf-8");
}

export const MemoryPlugin: Plugin = async ({ client, $, app }) => {
  return {
    tool: {
      execute: {
        before: async (input, output) => {
          // Intercept custom memory tool calls
          const toolName = input.tool?.toLowerCase();

          if (toolName === "save_memory") {
            const { name, description, type, content } = output.args as Record<string, string>;
            if (!name || !description || !type || !content) {
              throw new Error("save_memory requires: name, description, type, content");
            }
            ensureMemoryDir();
            const filename = `${slugify(name)}.md`;
            const filepath = join(MEMORY_DIR, filename);
            const entry: MemoryEntry = {
              name,
              description,
              type: type as MemoryEntry["type"],
              content,
            };
            writeFileSync(filepath, buildFrontmatter(entry), "utf-8");
            updateIndex("add", filename, name, description);
            return;
          }

          if (toolName === "delete_memory") {
            const { filename } = output.args as Record<string, string>;
            if (!filename) {
              throw new Error("delete_memory requires: filename");
            }
            // Validate: only allow simple filenames, no path traversal
            const safeName = filename.replace(/[^a-zA-Z0-9_.-]/g, "");
            if (safeName !== filename || filename.includes("..")) {
              throw new Error("delete_memory: invalid filename (no path traversal allowed)");
            }
            const filepath = resolve(MEMORY_DIR, safeName);
            // Ensure resolved path is within MEMORY_DIR
            if (!filepath.startsWith(MEMORY_DIR)) {
              throw new Error("delete_memory: path traversal detected");
            }
            if (existsSync(filepath)) {
              unlinkSync(filepath);
              updateIndex("remove", safeName, "", "");
            }
            return;
          }
        },
      },
    },
  };
};

export default MemoryPlugin;
