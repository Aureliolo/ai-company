import { useCallback, useRef, useState } from 'react'
import YAML from 'js-yaml'
import type { SettingEntry } from '@/api/types'
import { Button } from '@/components/ui/button'

export interface CodeEditorPanelProps {
  entries: SettingEntry[]
  onSave: (changes: Map<string, string>) => Promise<void>
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

function parseText(text: string, format: CodeFormat): Record<string, Record<string, string>> {
  if (format === 'json') {
    const parsed: unknown = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('JSON must be an object at the top level')
    }
    return parsed as Record<string, Record<string, string>>
  }
  const parsed = YAML.load(text, { schema: YAML.CORE_SCHEMA })
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('YAML must be a mapping (object) at the top level')
  }
  return parsed as Record<string, Record<string, string>>
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
          // Keep text as-is if conversion fails
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
    try {
      const parsed = parseText(text, format)
      const original = entriesToObject(entries)

      // Diff: find changed values
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

      await onSave(changes)
      setDirty(false)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : `Failed to parse ${format.toUpperCase()}`)
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
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            format === 'json'
              ? 'bg-accent/10 text-accent'
              : 'text-text-muted hover:text-foreground'
          }`}
        >
          JSON
        </button>
        <button
          type="button"
          onClick={() => handleFormatChange('yaml')}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            format === 'yaml'
              ? 'bg-accent/10 text-accent'
              : 'text-text-muted hover:text-foreground'
          }`}
        >
          YAML
        </button>
      </div>

      <textarea
        value={text}
        onChange={handleChange}
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
