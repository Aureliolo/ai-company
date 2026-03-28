import { useCallback, useRef, useState } from 'react'
import YAML from 'js-yaml'
import type { SettingEntry } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MAX_EDITOR_BYTES = 65_536

export interface CodeEditorPanelProps {
  entries: SettingEntry[]
  onSave: (changes: Map<string, string>) => Promise<Set<string>>
  saving: boolean
}

type CodeFormat = 'json' | 'yaml'

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

function parseText(text: string, format: CodeFormat): Record<string, Record<string, unknown>> {
  if (text.length > MAX_EDITOR_BYTES) {
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

export function CodeEditorPanel({ entries, onSave, saving }: CodeEditorPanelProps) {
  const [format, setFormat] = useState<CodeFormat>('json')
  const [text, setText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  // Sync from entries when not dirty
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
      setFormat(newFormat)
      if (!dirty) {
        setText(serializeEntries(entries, newFormat))
      } else {
        // Try to convert existing text to new format
        try {
          const parsed = parseText(text, format)
          if (newFormat === 'json') {
            setText(JSON.stringify(parsed, null, 2))
          } else {
            setText(YAML.dump(parsed, { indent: 2, lineWidth: 120, noRefs: true, sortKeys: false }))
          }
          setParseError(null)
        } catch {
          setParseError(`Cannot convert to ${newFormat.toUpperCase()}: fix syntax errors first`)
          setFormat(format) // revert format toggle
        }
      }
    },
    [dirty, entries, format, text],
  )

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    setDirty(true)
    setParseError(null)
  }, [])

  const handleSave = useCallback(async () => {
    // Step 1: parse the text
    let parsed: Record<string, Record<string, unknown>>
    try {
      parsed = parseText(text, format)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : `Failed to parse ${format.toUpperCase()}`)
      return
    }

    const original = entriesToObject(entries)

    // Step 2: detect removed keys (present in original but absent in parsed)
    const removedKeys: string[] = []
    for (const [ns, keys] of Object.entries(original)) {
      const parsedNs = parsed[ns]
      if (!parsedNs) {
        removedKeys.push(...Object.keys(keys).map((k) => `${ns}/${k}`))
      } else {
        for (const key of Object.keys(keys)) {
          if (!(key in parsedNs)) {
            removedKeys.push(`${ns}/${key}`)
          }
        }
      }
    }
    if (removedKeys.length > 0) {
      setParseError(
        `Cannot remove settings via code editor. Use the GUI to reset individual settings. ` +
        `Removed: ${removedKeys.join(', ')}`,
      )
      return
    }

    // Step 3: diff and find changed values
    const changes = new Map<string, string>()
    for (const [ns, keys] of Object.entries(parsed)) {
      const origNs = original[ns] ?? {}
      for (const [key, value] of Object.entries(keys)) {
        const strValue = typeof value === 'string' ? value : JSON.stringify(value)
        if (origNs[key] !== strValue) {
          changes.set(`${ns}/${key}`, strValue)
        }
      }
    }

    if (changes.size === 0) {
      setDirty(false)
      return
    }

    // Step 4: save -- network/API errors surfaced via toast by onSave
    const failedKeys = await onSave(changes)
    if (failedKeys.size === 0) {
      setDirty(false)
    } else {
      setParseError(`${failedKeys.size} setting(s) failed to save. Please review and try again.`)
    }
  }, [text, format, entries, onSave])

  const handleReset = useCallback(() => {
    setText(serializeEntries(entries, format))
    setDirty(false)
    setParseError(null)
  }, [entries, format])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => handleFormatChange('json')}
          className={cn(
            'rounded px-2.5 py-1 text-xs font-medium transition-colors',
            format === 'json' ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-foreground',
          )}
        >
          JSON
        </button>
        <button
          type="button"
          onClick={() => handleFormatChange('yaml')}
          className={cn(
            'rounded px-2.5 py-1 text-xs font-medium transition-colors',
            format === 'yaml' ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-foreground',
          )}
        >
          YAML
        </button>
      </div>

      <textarea
        value={text}
        onChange={handleChange}
        rows={20}
        className="w-full min-h-96 rounded-lg border border-border bg-surface p-4 font-mono text-sm text-foreground outline-none focus:ring-2 focus:ring-accent resize-y"
        spellCheck={false}
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
