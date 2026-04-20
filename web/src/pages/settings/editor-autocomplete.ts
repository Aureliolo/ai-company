/**
 * CodeMirror autocomplete extension for the Settings code editor.
 *
 * Provides schema-aware completions: namespace keys at top level,
 * setting keys inside namespaces, and enum values at value positions.
 */

import {
  autocompletion,
  type CompletionContext,
  type CompletionResult,
} from '@codemirror/autocomplete'
import type { Extension } from '@codemirror/state'
import type { SettingEntry, SettingNamespace, SettingType } from '@/api/types/settings'

// ── Completion schema ─────────────────────────────────────────

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

// ── JSON completion source ────────────────────────────────────

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

    // Walk backwards to determine context.
    // braceDepth counts unmatched '{' seen while scanning backward.
    // The first unmatched '{' is the innermost enclosing object.
    for (let i = pos - 1; i >= 0; i--) {
      const ch = text[i]
      if (ch === '{') {
        braceDepth++
        if (braceDepth === 1) {
          // First enclosing '{' -- check if it belongs to a namespace
          const preceding = text.slice(0, i).trimEnd()
          const nsMatch = /"(\w+)"\s*:\s*$/.exec(preceding)
          if (nsMatch) {
            // We're inside a namespace object (e.g. "api": { | })
            currentNamespace = nsMatch[1] ?? null
          }
          // If no nsMatch, we're at the root object level
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

    if (currentNamespace) {
      // Inside a namespace -- suggest setting keys
      const keyInfo = schema.keys.get(currentNamespace)
      if (!keyInfo) return null
      return {
        from,
        options: keyInfo.map((k) => ({
          label: k.key,
          type: 'property',
          detail: k.enumValues.length > 0
            ? `${k.type} (${k.enumValues.join(' | ')})`
            : k.type,
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

// ── YAML completion source ────────────────────────────────────

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
    const valueMatch = /^\s+(\w[\w_]*)\s*:\s*(\S*)$/.exec(beforeOnLine)
    if (valueMatch && indent > 0) {
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

    if (indent > 0) {
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
          detail: k.enumValues.length > 0
            ? `${k.type} (${k.enumValues.join(' | ')})`
            : k.type,
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

// ── Extension factory ─────────────────────────────────────────

let _cachedEntries: SettingEntry[] | null = null
let _cachedSchema: CompletionSchemaInfo | null = null

function getOrBuildSchema(
  entries: SettingEntry[],
): CompletionSchemaInfo {
  if (_cachedEntries === entries && _cachedSchema) {
    return _cachedSchema
  }
  _cachedSchema = buildCompletionSchema(entries)
  _cachedEntries = entries
  return _cachedSchema
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
        const schema = getOrBuildSchema(entries)
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
