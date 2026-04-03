import { useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { LazyCodeMirrorEditor } from '@/components/ui/lazy-code-mirror-editor'

export interface ExternalTriggerConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function ExternalTriggerConfig({ config, onChange, disabled }: ExternalTriggerConfigProps) {
  const transitionEvent = (config.transition_event as string) ?? ''
  const [rawJson, setRawJson] = useState(() => JSON.stringify(config.sources ?? [], null, 2))
  const [jsonError, setJsonError] = useState<string | null>(null)

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-sm font-medium text-foreground">Event Sources</p>
        <p className="mb-2 text-xs text-text-secondary">
          JSON array of source definitions (e.g. webhook, git_event)
        </p>
        <LazyCodeMirrorEditor
          value={rawJson}
          onChange={(val) => {
            setRawJson(val)
            try {
              const parsed: unknown = JSON.parse(val)
              onChange({ ...config, sources: parsed })
              setJsonError(null)
            } catch {
              setJsonError('Invalid JSON')
            }
          }}
          language="json"
          readOnly={disabled}
          aria-label="Sources JSON"
          className="max-h-48"
        />
        {jsonError && (
          <p className="mt-1 text-xs text-danger">{jsonError}</p>
        )}
      </div>

      <InputField
        label="Transition Event"
        value={transitionEvent}
        onChange={(e) => onChange({ ...config, transition_event: e.target.value })}
        disabled={disabled}
        hint="External event that triggers sprint auto-transition (e.g. deploy_complete)"
      />
    </div>
  )
}
