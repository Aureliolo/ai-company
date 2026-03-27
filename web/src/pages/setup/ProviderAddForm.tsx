import { useCallback, useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/utils/errors'
import type { ProviderPreset, TestConnectionResponse } from '@/api/types'

export interface ProviderAddFormProps {
  presets: readonly ProviderPreset[]
  onAdd: (presetName: string, name: string, apiKey?: string) => Promise<void>
  onTest: (name: string) => Promise<TestConnectionResponse>
}

export function ProviderAddForm({ presets, onAdd, onTest }: ProviderAddFormProps) {
  const [selectedPreset, setSelectedPreset] = useState('')
  const [providerName, setProviderName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cloudPresets = presets.filter((p) => p.auth_type !== 'none')

  const handleTest = useCallback(async () => {
    if (!providerName.trim()) return
    setTesting(true)
    setError(null)
    try {
      const result = await onTest(providerName.trim())
      setTestResult(result)
    } catch (err) {
      console.error('ProviderAddForm: test connection failed:', err)
      setError(getErrorMessage(err))
    } finally {
      setTesting(false)
    }
  }, [providerName, onTest])

  const handleAdd = useCallback(async () => {
    if (!selectedPreset || !providerName.trim()) return
    setAdding(true)
    setError(null)
    try {
      await onAdd(selectedPreset, providerName.trim(), apiKey || undefined)
      // Reset form
      setSelectedPreset('')
      setProviderName('')
      setApiKey('')
      setTestResult(null)
    } catch (err) {
      console.error('ProviderAddForm: create provider failed:', err)
      setError(getErrorMessage(err))
    } finally {
      setAdding(false)
    }
  }, [selectedPreset, providerName, apiKey, onAdd])

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
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={testing || !providerName.trim()}
            >
              {testing ? 'Testing...' : 'Test Connection'}
            </Button>
            <Button
              size="sm"
              onClick={handleAdd}
              disabled={adding || !providerName.trim() || !selectedPreset}
            >
              {adding ? 'Creating...' : 'Create Provider'}
            </Button>
          </div>

          {testResult && (
            <div className={cn(
              'rounded-md border px-3 py-2 text-sm',
              testResult.success
                ? 'border-success/30 bg-success/5 text-success'
                : 'border-danger/30 bg-danger/5 text-danger',
            )}>
              {testResult.success
                ? `Connected! ${testResult.model_tested ? `Model: ${testResult.model_tested}` : ''} (${testResult.latency_ms}ms)`
                : `Failed: ${testResult.error ?? 'Unknown error'}`}
            </div>
          )}

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
