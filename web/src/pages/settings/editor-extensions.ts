/**
 * CodeMirror extensions for the Settings code editor:
 * - Diff gutter markers (changed/added/removed lines)
 * - Inline validation via @codemirror/lint (syntax + schema)
 * - Schema-aware autocomplete
 */

import {
  type Extension,
  RangeSetBuilder,
  StateField,
  StateEffect,
} from '@codemirror/state'
import {
  EditorView,
  gutter,
  GutterMarker,
} from '@codemirror/view'
import { linter, type Diagnostic } from '@codemirror/lint'
import {
  autocompletion,
  type CompletionContext,
  type CompletionResult,
} from '@codemirror/autocomplete'
import YAML from 'js-yaml'
import type { SettingEntry, SettingNamespace, SettingType } from '@/api/types'

// ── Diff gutter ────────────────────────────────────────────────

export type LineDiffKind = 'changed' | 'added' | 'removed'

export interface LineDiff {
  /** 1-based line number in the edited document. */
  line: number
  kind: LineDiffKind
}

/**
 * Simple line-by-line diff between the server text and the edited text.
 * Returns an array of diff markers for lines that differ.
 *
 * Removed lines are reported at the line number where the deletion
 * occurred in the edited document (clamped to the last line).
 */
export function computeLineDiff(
  serverText: string,
  editedText: string,
): LineDiff[] {
  const serverLines = serverText.split('\n')
  const editedLines = editedText.split('\n')
  const diffs: LineDiff[] = []
  const maxLen = Math.max(serverLines.length, editedLines.length)

  for (let i = 0; i < maxLen; i++) {
    const s = serverLines[i]
    const e = editedLines[i]
    if (s === undefined) {
      // Line exists only in edited -- added
      diffs.push({ line: i + 1, kind: 'added' })
    } else if (e === undefined) {
      // Line exists only in server -- removed
      // Show at the last edited line (clamped)
      diffs.push({
        line: Math.min(i + 1, editedLines.length),
        kind: 'removed',
      })
    } else if (s !== e) {
      diffs.push({ line: i + 1, kind: 'changed' })
    }
  }

  return diffs
}

// Gutter markers using design-token CSS variables

class DiffGutterMarker extends GutterMarker {
  constructor(readonly kind: LineDiffKind) {
    super()
  }

  override toDOM(): HTMLElement {
    const el = document.createElement('span')
    el.className = `cm-diff-marker cm-diff-marker-${this.kind}`
    el.setAttribute('aria-hidden', 'true')
    return el
  }
}

const changedMarker = new DiffGutterMarker('changed')
const addedMarker = new DiffGutterMarker('added')
const removedMarker = new DiffGutterMarker('removed')

function markerForKind(kind: LineDiffKind): DiffGutterMarker {
  switch (kind) {
    case 'changed': return changedMarker
    case 'added': return addedMarker
    case 'removed': return removedMarker
  }
}

// State effect + field to store diff data

const setDiffEffect = StateEffect.define<LineDiff[]>()

const diffField = StateField.define<LineDiff[]>({
  create: () => [],
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setDiffEffect)) return effect.value
    }
    return value
  },
})

/**
 * Dispatch new diff data into the editor.
 * Call this whenever serverText or editedText changes.
 */
export function dispatchDiff(
  view: EditorView,
  serverText: string,
  editedText: string,
): void {
  const diffs = computeLineDiff(serverText, editedText)
  view.dispatch({ effects: setDiffEffect.of(diffs) })
}

// Gutter styling using design tokens
const diffGutterTheme = EditorView.theme({
  '.cm-diff-gutter': {
    width: '6px',
    marginRight: '2px',
  },
  '.cm-diff-marker': {
    display: 'inline-block',
    width: '4px',
    height: '100%',
    borderRadius: '1px',
  },
  '.cm-diff-marker-changed': {
    backgroundColor: 'var(--so-accent)',
  },
  '.cm-diff-marker-added': {
    backgroundColor: 'var(--so-success)',
  },
  '.cm-diff-marker-removed': {
    backgroundColor: 'var(--so-danger)',
  },
})

/**
 * CodeMirror gutter extension that shows colored markers for
 * changed/added/removed lines relative to the server version.
 */
export function diffGutterExtension(): Extension {
  return [
    diffField,
    gutter({
      class: 'cm-diff-gutter',
      markers: (view) => {
        const diffs = view.state.field(diffField)
        const builder = new RangeSetBuilder<GutterMarker>()
        const doc = view.state.doc

        // Sort diffs by line to satisfy RangeSetBuilder ordering
        const sorted = [...diffs].sort((a, b) => a.line - b.line)
        const seen = new Set<number>()

        for (const diff of sorted) {
          // Clamp to valid line range
          const lineNum = Math.max(1, Math.min(diff.line, doc.lines))
          if (seen.has(lineNum)) continue
          seen.add(lineNum)
          const lineObj = doc.line(lineNum)
          builder.add(lineObj.from, lineObj.from, markerForKind(diff.kind))
        }

        return builder.finish()
      },
    }),
    diffGutterTheme,
  ]
}

// ── Inline validation (linter) ─────────────────────────────────

/**
 * Schema lookup built from SettingEntry[].
 * Maps "namespace/key" to definition metadata for validation.
 */
interface SchemaInfo {
  knownNamespaces: Set<string>
  /** Maps "namespace" -> Set of known keys. */
  namespaceKeys: Map<string, Set<string>>
  /** Maps "namespace/key" -> SettingType for type validation. */
  keyTypes: Map<string, SettingType>
}

function buildSchemaInfo(entries: SettingEntry[]): SchemaInfo {
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

/**
 * Attempts to find the character position of a JSON key in the document.
 * Returns { from, to } spanning the key string (including quotes).
 */
function findJsonKeyPosition(
  text: string,
  namespace: string,
  key?: string,
): { from: number; to: number } | null {
  // Search for the key pattern: "keyName":
  const searchKey = key ?? namespace
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const pattern = new RegExp(`"${escapeRegex(searchKey)}"\\s*:`)
  const match = pattern.exec(text)
  if (match) {
    return { from: match.index, to: match.index + searchKey.length + 2 }
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
  const searchKey = key ?? namespace
  // YAML keys at indentation level: "keyName:"
  // eslint-disable-next-line security/detect-non-literal-regexp -- input is escaped via escapeRegex
  const pattern = new RegExp(`^(\\s*)${escapeRegex(searchKey)}\\s*:`, 'm')
  const match = pattern.exec(text)
  if (match) {
    const offset = match.index + (match[1]?.length ?? 0)
    return { from: offset, to: offset + searchKey.length }
  }
  return null
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Validate parsed settings against the schema, returning diagnostics
 * for unknown namespaces and unknown keys.
 */
function validateSchema(
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

// ── Schema-aware autocomplete ──────────────────────────────────

interface CompletionSchemaInfo {
  /** All known namespaces. */
  namespaces: SettingNamespace[]
  /** Maps namespace -> array of { key, type, description, enumValues }. */
  keys: Map<string, Array<{
    key: string
    type: SettingType
    description: string
    enumValues: readonly string[]
  }>>
}

function buildCompletionSchema(entries: SettingEntry[]): CompletionSchemaInfo {
  const nsSet = new Set<SettingNamespace>()
  const keys = new Map<string, Array<{
    key: string
    type: SettingType
    description: string
    enumValues: readonly string[]
  }>>()

  for (const entry of entries) {
    const ns = entry.definition.namespace
    nsSet.add(ns)
    if (!keys.has(ns)) keys.set(ns, [])
    keys.get(ns)!.push({
      key: entry.definition.key,
      type: entry.definition.type,
      description: entry.definition.description,
      enumValues: entry.definition.enum_values,
    })
  }

  return {
    namespaces: [...nsSet].sort(),
    keys,
  }
}

/**
 * Determine the current context for autocomplete:
 * - At top level: suggest namespace keys
 * - Inside a namespace: suggest setting keys
 * - At a value position for an enum key: suggest enum values
 */
function jsonCompletionSource(
  schema: CompletionSchemaInfo,
): (ctx: CompletionContext) => CompletionResult | null {
  return (ctx: CompletionContext) => {
    const text = ctx.state.doc.toString()
    const pos = ctx.pos

    // Get the text before cursor for context analysis
    const before = text.slice(0, pos)

    // Check if we're typing a key (after { or , and before :)
    // Determine nesting depth to know if we're at namespace or key level
    let braceDepth = 0
    let currentNamespace: string | null = null

    // Walk backwards to determine context
    for (let i = pos - 1; i >= 0; i--) {
      const ch = text[i]
      if (ch === '{') {
        braceDepth++
        if (braceDepth === 1) {
          // We're inside the root object -- suggest namespaces
          break
        }
        if (braceDepth === 2) {
          // We're inside a namespace object -- find which one
          // Look backwards from this opening brace to find the key
          const preceding = text.slice(0, i).trimEnd()
          const nsMatch = /"(\w+)"\s*:\s*$/.exec(preceding)
          if (nsMatch) {
            currentNamespace = nsMatch[1] ?? null
          }
          break
        }
      } else if (ch === '}') {
        braceDepth--
      }
    }

    // Check if we're in a string value position (after "key": )
    // Look for pattern: "someKey": "| (cursor in a value string)
    const valueMatch = /"(\w+)"\s*:\s*"([^"]*?)$/.exec(before)
    if (valueMatch && currentNamespace) {
      const settingKey = valueMatch[1] ?? ''
      const partial = valueMatch[2] ?? ''
      const keyInfo = schema.keys.get(currentNamespace)
      const setting = keyInfo?.find((k) => k.key === settingKey)
      if (setting && setting.enumValues.length > 0) {
        const from = pos - partial.length
        return {
          from,
          options: setting.enumValues.map((val) => ({
            label: val,
            type: 'enum',
            detail: `${currentNamespace}/${settingKey}`,
          })),
        }
      }
      return null
    }

    // Check if we're typing a key name (inside quotes at key position)
    // Pattern: after { or , or newline, possibly whitespace, then "partial
    const keyMatch = /(?:^|[{,])\s*"(\w*)$/.exec(before)
    if (!keyMatch) return null

    const partial = keyMatch[1] ?? ''
    const from = pos - partial.length

    if (braceDepth >= 2 && currentNamespace) {
      // Inside a namespace -- suggest setting keys
      const keyInfo = schema.keys.get(currentNamespace)
      if (!keyInfo) return null
      return {
        from,
        options: keyInfo.map((k) => ({
          label: k.key,
          type: 'property',
          detail: `${k.type}${k.enumValues.length > 0 ? ` (${k.enumValues.join(' | ')})` : ''}`,
          info: k.description,
        })),
      }
    }

    // At root level -- suggest namespaces
    return {
      from,
      options: schema.namespaces.map((ns) => ({
        label: ns,
        type: 'keyword',
        detail: 'namespace',
        info: `Settings namespace: ${ns}`,
      })),
    }
  }
}

function yamlCompletionSource(
  schema: CompletionSchemaInfo,
): (ctx: CompletionContext) => CompletionResult | null {
  return (ctx: CompletionContext) => {
    const text = ctx.state.doc.toString()
    const pos = ctx.pos

    // Get the current line and text before cursor
    const lineObj = ctx.state.doc.lineAt(pos)
    const lineText = lineObj.text
    const colPos = pos - lineObj.from
    const beforeOnLine = lineText.slice(0, colPos)

    // Determine indentation level
    const indentMatch = /^(\s*)/.exec(lineText)
    const indent = indentMatch?.[1]?.length ?? 0

    // Check if we're typing a value after "key: " for enum autocomplete
    const valueMatch = /^\s{2,}(\w[\w_]*)\s*:\s*(\S*)$/.exec(beforeOnLine)
    if (valueMatch && indent >= 2) {
      const settingKey = valueMatch[1] ?? ''
      const partial = valueMatch[2] ?? ''

      // Find the namespace by looking at the previous unindented key
      const linesAbove = text.slice(0, lineObj.from).split('\n')
      let ns: string | null = null
      for (let i = linesAbove.length - 1; i >= 0; i--) {
        const nsMatch = /^(\w[\w_]*)\s*:/.exec(linesAbove[i] ?? '')
        if (nsMatch) {
          ns = nsMatch[1] ?? null
          break
        }
      }

      if (ns) {
        const keyInfo = schema.keys.get(ns)
        const setting = keyInfo?.find((k) => k.key === settingKey)
        if (setting && setting.enumValues.length > 0) {
          const from = pos - partial.length
          return {
            from,
            options: setting.enumValues.map((val) => ({
              label: val,
              type: 'enum',
              detail: `${ns}/${settingKey}`,
            })),
          }
        }
      }
      return null
    }

    // Check if we're typing a key
    const keyTyping = beforeOnLine.trimStart()
    // Only complete if we haven't typed a colon yet
    if (keyTyping.includes(':')) return null

    const partial = keyTyping
    const from = pos - partial.length

    if (indent >= 2) {
      // Indented -- inside a namespace, suggest setting keys
      const linesAbove = text.slice(0, lineObj.from).split('\n')
      let ns: string | null = null
      for (let i = linesAbove.length - 1; i >= 0; i--) {
        const nsMatch = /^(\w[\w_]*)\s*:/.exec(linesAbove[i] ?? '')
        if (nsMatch) {
          ns = nsMatch[1] ?? null
          break
        }
      }
      if (!ns) return null
      const keyInfo = schema.keys.get(ns)
      if (!keyInfo) return null
      return {
        from,
        options: keyInfo.map((k) => ({
          label: k.key,
          type: 'property',
          detail: `${k.type}${k.enumValues.length > 0 ? ` (${k.enumValues.join(' | ')})` : ''}`,
          info: k.description,
          apply: `${k.key}: `,
        })),
      }
    }

    // Top level -- suggest namespaces
    return {
      from,
      options: schema.namespaces.map((ns) => ({
        label: ns,
        type: 'keyword',
        detail: 'namespace',
        info: `Settings namespace: ${ns}`,
        apply: `${ns}:\n  `,
      })),
    }
  }
}

/**
 * Create a schema-aware autocomplete extension for the settings editor.
 *
 * @param getFormat - Returns the current editor format
 * @param getEntries - Returns the current SettingEntry[] for schema
 */
export function settingsAutocompleteExtension(
  getFormat: () => 'json' | 'yaml',
  getEntries: () => SettingEntry[],
): Extension {
  return autocompletion({
    override: [
      (ctx: CompletionContext) => {
        const entries = getEntries()
        if (entries.length === 0) return null
        const schema = buildCompletionSchema(entries)
        const format = getFormat()
        const source = format === 'json'
          ? jsonCompletionSource(schema)
          : yamlCompletionSource(schema)
        return source(ctx)
      },
    ],
    activateOnTyping: true,
  })
}
