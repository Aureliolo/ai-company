import { useCallback, useMemo, useRef, useState } from 'react'
import YAML from 'js-yaml'
import type { SettingEntry } from '@/api/types'
import { Button } from '@/components/ui/button'
import { CodeMirrorEditor, type CodeMirrorEditorProps } from '@/components/ui/code-mirror-editor'
import { SegmentedControl } from '@/components/ui/segmented-control'

const MAX_EDITOR_BYTES = 65_536

export interface CodeEditorPanelProps {
  entries: SettingEntry[]
  onSave: (changes: Map<string, string>) => Promise<Set<string>>
  saving: boolean
  onDirtyChange?: (dirty: boolean) => void
}

type CodeFormat = CodeMirrorEditorProps['language']

const FORMAT_OPTIONS = [
  { value: 'json' as const, label: 'JSON' },
  { value: 'yaml' as const, label: 'YAML' },
]

function entriesToObject(entries: SettingEntry[]): Record<string, Record<string, string>> {
  const obj: Record<string, Record<string, string>> = {}
  for (const entry of entries) {
    const ns = entry.definition.namespace
    if (!obj[ns]) obj[ns] = {}
    obj[ns][entry.definition.key] = entry.value
  }
  return obj
}

function serializeEntries(entries: SettingEntry[], format: CodeFormat): string {
  const obj = entriesToObject(entries)
  if (format === 'json') {
    return JSON.stringify(obj, null, 2)
  }
  return YAML.dump(obj, { indent: 2, lineWidth: 120, noRefs: true, sortKeys: false })
}

type ParsedSettings = Record<string, Record<string, unknown>>

/** Find keys present in original but absent in parsed. */
function detectRemovedKeys(
  original: Record<string, Record<string, string>>,
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
function buildChanges(
  parsed: ParsedSettings,
  original: Record<string, Record<string, string>>,
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
      if (origNs[key] !== strValue) {
        changes.set(ck, strValue)
      }
    }
  }
  return { changes, unknownKeys, envKeys }
}

function parseText(text: string, format: CodeFormat): ParsedSettings {
  const byteLength = new TextEncoder().encode(text).length
  if (byteLength > MAX_EDITOR_BYTES) {
    throw new Error(`Input too large (max ${MAX_EDITOR_BYTES / 1024} KiB)`)
  }

  const raw: unknown = format === 'json'
    ? JSON.parse(text)
    : YAML.load(text, { schema: YAML.CORE_SCHEMA })

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

export function CodeEditorPanel({ entries, onSave, saving, onDirtyChange }: CodeEditorPanelProps) {
  const [format, setFormat] = useState<CodeFormat>('json')
  const [text, setText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  const entryLookup = useMemo(() => {
    const map = new Map<string, SettingEntry>()
    for (const e of entries) {
      map.set(`${e.definition.namespace}/${e.definition.key}`, e)
    }
    return map
  }, [entries])

  const updateDirty = useCallback((next: boolean) => {
    setDirty(next)
    onDirtyChange?.(next)
  }, [onDirtyChange])

  // Sync from entries during render (not useEffect) to avoid a flash of stale
  // content. Only syncs when user hasn't made edits (dirty=false).
  const prevEntriesRef = useRef<typeof entries | undefined>(undefined)
  if (entries !== prevEntriesRef.current) {
    prevEntriesRef.current = entries
    if (!dirty) {
      setText(serializeEntries(entries, format))
      setParseError(null)
    }
  }

  const handleFormatChange = useCallback(
    (newFormat: CodeFormat) => {
      if (!dirty) {
        setFormat(newFormat)
        try {
          setText(serializeEntries(entries, newFormat))
        } catch (err) {
          setParseError(err instanceof Error ? err.message : `Failed to serialize as ${newFormat.toUpperCase()}`)
        }
      } else {
        // Try to convert existing text to new format
        try {
          const parsed = parseText(text, format)
          setFormat(newFormat)
          if (newFormat === 'json') {
            setText(JSON.stringify(parsed, null, 2))
          } else {
            setText(YAML.dump(parsed, { indent: 2, lineWidth: 120, noRefs: true, sortKeys: false }))
          }
          setParseError(null)
        } catch {
          setParseError(`Cannot convert to ${newFormat.toUpperCase()}: fix syntax errors first`)
        }
      }
    },
    [dirty, entries, format, text],
  )

  const handleChange = useCallback((value: string) => {
    setText(value)
    updateDirty(true)
    setParseError(null)
  }, [updateDirty])

  const handleSave = useCallback(async () => {
    let parsed: ParsedSettings
    try {
      parsed = parseText(text, format)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : `Failed to parse ${format.toUpperCase()}`)
      return
    }

    const original = entriesToObject(entries)
    const removed = detectRemovedKeys(original, parsed)
    if (removed.length > 0) {
      setParseError(`Cannot remove settings via code editor. Use GUI to reset. Removed: ${removed.join(', ')}`)
      return
    }

    const { changes, unknownKeys, envKeys } = buildChanges(parsed, original, entryLookup)
    if (unknownKeys.length > 0) {
      setParseError(`Unknown setting(s): ${unknownKeys.join(', ')}`)
      return
    }
    if (envKeys.length > 0) {
      setParseError(`Cannot edit env-sourced setting(s): ${envKeys.join(', ')}`)
      return
    }
    if (changes.size === 0) { updateDirty(false); return }

    const textBeforeSave = text
    let failedKeys: Set<string>
    try {
      failedKeys = await onSave(changes)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Save failed unexpectedly')
      return
    }
    if (failedKeys.size === 0) {
      if (text === textBeforeSave) updateDirty(false)
    } else {
      setParseError(`${failedKeys.size} setting(s) failed to save.`)
    }
  }, [text, format, entries, entryLookup, onSave, updateDirty])

  const handleReset = useCallback(() => {
    try {
      setText(serializeEntries(entries, format))
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to serialize settings')
      return
    }
    updateDirty(false)
    setParseError(null)
  }, [entries, format, updateDirty])

  return (
    <div className="space-y-3">
      <SegmentedControl<CodeFormat>
        label="Editor format"
        options={FORMAT_OPTIONS}
        value={format}
        onChange={handleFormatChange}
        disabled={saving}
      />

      <CodeMirrorEditor
        value={text}
        onChange={handleChange}
        language={format}
        readOnly={saving}
        aria-label={`${format.toUpperCase()} editor`}
      />

      {parseError && (
        <p className="text-xs text-danger" role="alert">{parseError}</p>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={!dirty || saving}>
          {saving ? 'Saving...' : `Save ${format.toUpperCase()}`}
        </Button>
        <Button variant="outline" onClick={handleReset} disabled={!dirty || saving}>
          Reset
        </Button>
        {dirty && <span className="text-xs text-warning">Unsaved changes</span>}
      </div>
    </div>
  )
}
