/**
 * Utility functions for the Settings code editor.
 *
 * Handles serialization, parsing, validation, and diffing of
 * settings entries in JSON/YAML format.
 *
 * Note: this module has a side effect (logger instance) for
 * structured error reporting in entriesToObject.
 */

import YAML from 'js-yaml'
import type { SettingEntry } from '@/api/types'
import type { CodeMirrorEditorProps } from '@/components/ui/code-mirror-editor'
import { createLogger } from '@/lib/logger'

const log = createLogger('settings')

export const MAX_EDITOR_BYTES = 65_536

export type CodeFormat = Extract<
  CodeMirrorEditorProps['language'],
  'json' | 'yaml'
>

export type ParsedSettings = Record<string, Record<string, unknown>>

const UNSAFE_KEYS = new Set(['__proto__', 'prototype', 'constructor'])

export function entriesToObject(entries: SettingEntry[]): ParsedSettings {
  const obj = Object.create(null) as ParsedSettings
  for (const entry of entries) {
    const ns = entry.definition.namespace
    const key = entry.definition.key
    if (UNSAFE_KEYS.has(ns) || UNSAFE_KEYS.has(key)) continue
    if (!obj[ns]) obj[ns] = Object.create(null) as Record<string, unknown>
    // Parse JSON-type values so they embed as real objects/arrays
    // instead of escaped string representations (e.g. "[\"http://...\"]")
    if (entry.definition.type === 'json') {
      try {
        obj[ns][key] = JSON.parse(entry.value)
      } catch (err) {
        log.warn('Failed to parse JSON for setting:', `${ns}/${key}`, err)
        obj[ns][key] = entry.value
      }
    } else {
      obj[ns][key] = entry.value
    }
  }
  return obj
}

export function serializeEntries(entries: SettingEntry[], format: CodeFormat): string {
  const obj = entriesToObject(entries)
  if (format === 'json') {
    return JSON.stringify(obj, null, 2)
  }
  if (format === 'yaml') {
    return YAML.dump(obj, { indent: 2, lineWidth: 120, noRefs: true, sortKeys: false })
  }
  throw new Error(`Unsupported format: ${String(format)}`)
}

/** Find keys present in original but absent in parsed. */
export function detectRemovedKeys(
  original: Record<string, Record<string, unknown>>,
  parsed: ParsedSettings,
): string[] {
  const removed: string[] = []
  for (const [ns, keys] of Object.entries(original)) {
    const parsedNs = parsed[ns]
    if (!parsedNs) {
      removed.push(
        ...Object.keys(keys).map((k) => `${ns}/${k}`),
      )
    } else {
      for (const key of Object.keys(keys)) {
        if (!(key in parsedNs)) removed.push(`${ns}/${key}`)
      }
    }
  }
  return removed
}

/** Validate and diff parsed settings against original. */
export function buildChanges(
  parsed: ParsedSettings,
  original: Record<string, Record<string, unknown>>,
  entryLookup: ReadonlyMap<string, SettingEntry>,
): {
  changes: Map<string, string>
  unknownKeys: string[]
  envKeys: string[]
} {
  const changes = new Map<string, string>()
  const unknownKeys: string[] = []
  const envKeys: string[] = []
  for (const [ns, keys] of Object.entries(parsed)) {
    const origNs = original[ns] ?? {}
    for (const [key, value] of Object.entries(keys)) {
      const ck = `${ns}/${key}`
      const entry = entryLookup.get(ck)
      if (!entry) { unknownKeys.push(ck); continue }
      if (entry.source === 'env') { envKeys.push(ck); continue }
      const strValue = typeof value === 'string'
        ? value : JSON.stringify(value)
      const origValue = origNs[key]
      const origStr = typeof origValue === 'string'
        ? origValue : JSON.stringify(origValue)
      if (origStr !== strValue) {
        changes.set(ck, strValue)
      }
    }
  }
  return { changes, unknownKeys, envKeys }
}

export function parseText(text: string, format: CodeFormat): ParsedSettings {
  const byteLength = new TextEncoder().encode(text).length
  if (byteLength > MAX_EDITOR_BYTES) {
    throw new Error(`Input too large (max ${MAX_EDITOR_BYTES / 1024} KiB)`)
  }

  let raw: unknown
  if (format === 'json') {
    raw = JSON.parse(text)
  } else if (format === 'yaml') {
    // CORE_SCHEMA is intentional: disables !!js/function and !!js/regexp
    // tags that could execute arbitrary code. Do not change to
    // DEFAULT_SCHEMA.
    raw = YAML.load(text, { schema: YAML.CORE_SCHEMA })
  } else {
    throw new Error(`Unsupported format: ${String(format)}`)
  }

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error(`${format.toUpperCase()} must be an object at the top level`)
  }

  for (const [ns, nsValue] of Object.entries(raw as Record<string, unknown>)) {
    if (!nsValue || typeof nsValue !== 'object' || Array.isArray(nsValue)) {
      throw new Error(`Namespace "${ns}" must be an object, got ${typeof nsValue}`)
    }
  }

  return raw as Record<string, Record<string, unknown>>
}
