/**
 * CodeMirror linter extension for the Settings code editor.
 *
 * Provides debounced inline validation: syntax checking (JSON/YAML)
 * and schema validation against known setting namespaces and keys.
 */

import { type Extension } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { linter, type Diagnostic } from '@codemirror/lint'
import YAML from 'js-yaml'
import type { SettingEntry, SettingType } from '@/api/types/settings'

// ── Schema info ───────────────────────────────────────────────

/** @internal Exported for direct unit testing. */
export interface SchemaInfo {
  knownNamespaces: Set<string>
  /** Maps "namespace" -> Set of known keys. */
  namespaceKeys: Map<string, Set<string>>
  /** Maps "namespace/key" -> SettingType for type validation. */
  keyTypes: Map<string, SettingType>
}

/** @internal Exported for direct unit testing. */
export function buildSchemaInfo(entries: SettingEntry[]): SchemaInfo {
  const knownNamespaces = new Set<string>()
  const namespaceKeys = new Map<string, Set<string>>()
  const keyTypes = new Map<string, SettingType>()

  for (const entry of entries) {
    const ns = entry.definition.namespace
    knownNamespaces.add(ns)
    if (!namespaceKeys.has(ns)) namespaceKeys.set(ns, new Set())
    namespaceKeys.get(ns)!.add(entry.definition.key)
    keyTypes.set(`${ns}/${entry.definition.key}`, entry.definition.type)
  }

  return { knownNamespaces, namespaceKeys, keyTypes }
}

// ── Key position finders ──────────────────────────────────────

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Attempts to find the character position of a JSON key in the document.
 * Returns { from, to } spanning the key string (including quotes).
 */
function findJsonKeyPosition(
  text: string,
  namespace: string,
  key?: string,
): { from: number; to: number } | null {
  if (!key) {
    // Searching for a namespace -- first occurrence is fine
    // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
    const pattern = new RegExp(`"${escapeRegex(namespace)}"\\s*:`)
    const match = pattern.exec(text)
    if (match) {
      return { from: match.index, to: match.index + namespace.length + 2 }
    }
    return null
  }
  // Searching for a key within a namespace -- find the namespace first,
  // then search for the key within its scope to avoid false matches
  // in other namespaces with the same key name.
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const nsPattern = new RegExp(`"${escapeRegex(namespace)}"\\s*:\\s*\\{`)
  const nsMatch = nsPattern.exec(text)
  const searchFrom = nsMatch ? nsMatch.index + nsMatch[0].length : 0
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const keyPattern = new RegExp(`"${escapeRegex(key)}"\\s*:`)
  keyPattern.lastIndex = 0
  const sub = text.slice(searchFrom)
  const keyMatch = keyPattern.exec(sub)
  if (keyMatch) {
    const offset = searchFrom + keyMatch.index
    return { from: offset, to: offset + key.length + 2 }
  }
  return null
}

/**
 * Attempts to find the character position of a YAML key in the document.
 * Returns { from, to } spanning the key.
 */
function findYamlKeyPosition(
  text: string,
  namespace: string,
  key?: string,
): { from: number; to: number } | null {
  if (!key) {
    // Searching for a namespace (top-level, no indentation)
    // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
    const pattern = new RegExp(`^${escapeRegex(namespace)}\\s*:`, 'm')
    const match = pattern.exec(text)
    if (match) {
      return { from: match.index, to: match.index + namespace.length }
    }
    return null
  }
  // Searching for a key within a namespace -- find the namespace line first,
  // then search for the indented key after it.
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const nsPattern = new RegExp(`^${escapeRegex(namespace)}\\s*:`, 'm')
  const nsMatch = nsPattern.exec(text)
  const searchFrom = nsMatch ? nsMatch.index + nsMatch[0].length : 0
  const sub = text.slice(searchFrom)
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const keyPattern = new RegExp(`^(\\s+)["']?${escapeRegex(key)}["']?\\s*:`, 'm')
  const keyMatch = keyPattern.exec(sub)
  if (keyMatch) {
    const offset = searchFrom + keyMatch.index + (keyMatch[1]?.length ?? 0)
    return { from: offset, to: offset + key.length }
  }
  return null
}

// ── Schema validation ─────────────────────────────────────────

/**
 * Validate parsed settings against the schema, returning diagnostics
 * for unknown namespaces and unknown keys.
 *
 * @internal Exported for direct unit testing.
 */
export function validateSchema(
  parsed: Record<string, Record<string, unknown>>,
  schema: SchemaInfo,
  text: string,
  format: 'json' | 'yaml',
): Diagnostic[] {
  const diagnostics: Diagnostic[] = []
  const findKey = format === 'json' ? findJsonKeyPosition : findYamlKeyPosition

  for (const [ns, keys] of Object.entries(parsed)) {
    if (!schema.knownNamespaces.has(ns)) {
      const pos = findKey(text, ns)
      if (pos) {
        diagnostics.push({
          from: pos.from,
          to: pos.to,
          severity: 'warning',
          message: `Unknown namespace "${ns}"`,
        })
      }
      continue
    }

    if (!keys || typeof keys !== 'object') continue
    const knownKeys = schema.namespaceKeys.get(ns)
    if (!knownKeys) continue

    for (const key of Object.keys(keys)) {
      if (!knownKeys.has(key)) {
        const pos = findKey(text, ns, key)
        if (pos) {
          diagnostics.push({
            from: pos.from,
            to: pos.to,
            severity: 'warning',
            message: `Unknown setting key "${key}" in namespace "${ns}"`,
          })
        }
      }
    }
  }

  return diagnostics
}

// ── Theme ─────────────────────────────────────────────────────

const linterTheme = EditorView.theme({
  '.cm-diagnostic': {
    fontFamily: 'var(--so-font-mono)',
    fontSize: 'var(--so-text-body-sm)',
    padding: '2px 6px',
  },
  '.cm-diagnostic-error': {
    borderLeft: '3px solid var(--so-danger)',
  },
  '.cm-diagnostic-warning': {
    borderLeft: '3px solid var(--so-warning)',
  },
  '.cm-diagnostic-info': {
    borderLeft: '3px solid var(--so-accent)',
  },
  '.cm-lint-marker-error': {
    content: '""',
  },
  '.cm-lint-marker-warning': {
    content: '""',
  },
  '.cm-panel.cm-panel-lint': {
    backgroundColor: 'var(--so-bg-surface)',
    borderTop: '1px solid var(--so-border)',
    maxHeight: '120px',
    overflow: 'auto',
  },
  '.cm-panel.cm-panel-lint ul': {
    fontFamily: 'var(--so-font-mono)',
    fontSize: 'var(--so-text-body-sm)',
  },
  '.cm-panel.cm-panel-lint [aria-selected]': {
    backgroundColor: 'var(--so-bg-card)',
  },
  '.cm-tooltip-lint': {
    backgroundColor: 'var(--so-bg-surface)',
    border: '1px solid var(--so-border)',
    borderRadius: 'var(--so-radius-md)',
  },
})

// ── Extension factory ─────────────────────────────────────────

/**
 * Create a linter extension that validates JSON/YAML syntax
 * and flags unknown setting keys against the schema.
 *
 * @param getFormat - Returns the current editor format ('json' | 'yaml')
 * @param getEntries - Returns the current SettingEntry[] for schema validation
 */
export function settingsLinterExtension(
  getFormat: () => 'json' | 'yaml',
  getEntries: () => SettingEntry[],
): Extension {
  return [
    linter(
      (view) => {
        const text = view.state.doc.toString()
        if (!text.trim()) return []

        const format = getFormat()
        const diagnostics: Diagnostic[] = []

        // Phase 1: Syntax validation
        let parsed: Record<string, Record<string, unknown>>
        try {
          const raw: unknown = format === 'json'
            ? JSON.parse(text)
            : YAML.load(text, { schema: YAML.CORE_SCHEMA })

          if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
            diagnostics.push({
              from: 0,
              to: Math.min(text.length, 50),
              severity: 'error',
              message: `${format.toUpperCase()} must be an object at the top level`,
            })
            return diagnostics
          }

          parsed = raw as Record<string, Record<string, unknown>>
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Parse error'
          // Try to extract position from error message
          let from = 0
          let to = Math.min(text.length, 1)

          if (err instanceof SyntaxError) {
            // JSON.parse errors often include "at position N"
            const posMatch = /position\s+(\d+)/i.exec(msg)
            if (posMatch) {
              from = Math.min(Number(posMatch[1]), text.length)
              to = Math.min(from + 1, text.length)
            }
          }

          // js-yaml YAMLException includes mark with position
          if (
            err &&
            typeof err === 'object' &&
            'mark' in err &&
            typeof (err as { mark?: { position?: number } }).mark?.position === 'number'
          ) {
            const yamlErr = err as { mark: { position: number } }
            from = Math.min(yamlErr.mark.position, text.length)
            to = Math.min(from + 1, text.length)
          }

          diagnostics.push({
            from,
            to,
            severity: 'error',
            message: `Syntax error: ${msg}`,
          })
          return diagnostics
        }

        // Phase 2: Schema validation
        const entries = getEntries()
        if (entries.length > 0) {
          const schema = buildSchemaInfo(entries)
          const schemaErrors = validateSchema(parsed, schema, text, format)
          diagnostics.push(...schemaErrors)
        }

        return diagnostics
      },
      { delay: 300 },
    ),
    linterTheme,
  ]
}
