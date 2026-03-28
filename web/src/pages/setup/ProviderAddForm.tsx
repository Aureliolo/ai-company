import { useCallback, useMemo, useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/utils/errors'
import type { ProviderPreset, ProviderConfig } from '@/api/types'

export interface ProviderAddFormProps {
  presets: readonly ProviderPreset[]
  providers: Readonly<Record<string, ProviderConfig>>
  onAdd: (presetName: string, name: string, apiKey?: string) => Promise<void>
}

export function ProviderAddForm({ presets, providers, onAdd }: ProviderAddFormProps) {
  const [selectedPreset, setSelectedPreset] = useState('')
  const [providerName, setProviderName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cloudPresets = useMemo(
    () => presets.filter((p) => p.auth_type === 'api_key'),
    [presets],
  )

  const nameConflict = providerName.trim() !== '' && providerName.trim() in providers

  const handleAdd = useCallback(async () => {
    if (!selectedPreset || !providerName.trim() || nameConflict) return
    setAdding(true)
    setError(null)
    try {
      await onAdd(selectedPreset, providerName.trim(), apiKey || undefined)
      // Reset form
      setSelectedPreset('')
      setProviderName('')
      setApiKey('')
    } catch (err) {
      console.error('ProviderAddForm: create provider failed:', err)
      setError(getErrorMessage(err))
    } finally {
      setAdding(false)
    }
  }, [selectedPreset, providerName, apiKey, nameConflict, onAdd])

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">Add Cloud Provider</h3>
        <p className="text-xs text-muted-foreground">
          Connect a cloud LLM provider with your API key.
        </p>
      </div>

      <SelectField
        label="Provider Preset"
        options={cloudPresets.map((p) => ({
          value: p.name,
          label: `${p.display_name} (${p.auth_type})`,
        }))}
        value={selectedPreset}
        onChange={(val) => {
          setSelectedPreset(val)
          if (!providerName) {
            setProviderName(val)
          }
        }}
        placeholder="Select a provider type..."
      />

      {selectedPreset && (
        <>
          <InputField
            label="Provider Name"
            required
            value={providerName}
            onChange={(e) => setProviderName(e.currentTarget.value)}
            placeholder="my-provider"
            error={nameConflict ? `Provider '${providerName.trim()}' already exists` : null}
          />

          <InputField
            label="API Key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.currentTarget.value)}
            placeholder="sk-..."
            hint="Required for cloud providers"
          />

          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => void handleAdd()}
              disabled={adding || !providerName.trim() || !selectedPreset || nameConflict}
            >
              {adding ? 'Creating...' : 'Create Provider'}
            </Button>
          </div>

          {error && (
            <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}
        </>
      )}
    </div>
  )
}
