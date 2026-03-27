import { useCallback, useEffect, useMemo } from 'react'
import { StatusBadge } from '@/components/ui/status-badge'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateProvidersStep } from '@/utils/setup-validation'
import { ProviderProbeResults } from './ProviderProbeResults'
import { ProviderAddForm } from './ProviderAddForm'
import { Server } from 'lucide-react'

export function ProvidersStep() {
  const agents = useSetupWizardStore((s) => s.agents)
  const providers = useSetupWizardStore((s) => s.providers)
  const presets = useSetupWizardStore((s) => s.presets)
  const probeResults = useSetupWizardStore((s) => s.probeResults)
  const probing = useSetupWizardStore((s) => s.probing)
  const providersLoading = useSetupWizardStore((s) => s.providersLoading)
  const providersError = useSetupWizardStore((s) => s.providersError)

  const fetchProviders = useSetupWizardStore((s) => s.fetchProviders)
  const fetchPresets = useSetupWizardStore((s) => s.fetchPresets)
  const probeAllPresets = useSetupWizardStore((s) => s.probeAllPresets)
  const createProviderFromPreset = useSetupWizardStore((s) => s.createProviderFromPreset)
  const testProviderConnection = useSetupWizardStore((s) => s.testProviderConnection)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  // Fetch providers and presets on mount
  useEffect(() => {
    if (Object.keys(providers).length === 0 && !providersLoading) {
      fetchProviders()
    }
    if (presets.length === 0) {
      fetchPresets()
    }
  }, [providers, providersLoading, presets.length, fetchProviders, fetchPresets])

  // Auto-probe local presets
  useEffect(() => {
    if (presets.length > 0 && Object.keys(probeResults).length === 0 && !probing) {
      probeAllPresets()
    }
  }, [presets.length, probeResults, probing, probeAllPresets])

  // Track step completion
  const validation = useMemo(() => validateProvidersStep({ agents, providers }), [agents, providers])
  useEffect(() => {
    if (validation.valid) {
      markStepComplete('providers')
    } else {
      markStepIncomplete('providers')
    }
  }, [validation.valid, markStepComplete, markStepIncomplete])

  const handleAddPreset = useCallback(
    async (presetName: string) => {
      await createProviderFromPreset(presetName, presetName)
    },
    [createProviderFromPreset],
  )

  const handleAddCloud = useCallback(
    async (presetName: string, name: string, apiKey?: string) => {
      await createProviderFromPreset(presetName, name, apiKey)
    },
    [createProviderFromPreset],
  )

  if (providersLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    )
  }

  const providerEntries = Object.entries(providers)
  // Which providers do agents need?
  const neededProviders = new Set(agents.map((a) => a.model_provider).filter(Boolean))
  const missingProviders = [...neededProviders].filter((p) => !providers[p])

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Set Up Providers</h2>
        <p className="text-sm text-muted-foreground">
          Connect your LLM providers so agents can work.
        </p>
      </div>

      {providersError && (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {providersError}
        </div>
      )}

      {/* Missing provider warnings */}
      {missingProviders.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
          Agents need these providers: {missingProviders.join(', ')}
        </div>
      )}

      {/* Auto-detect results */}
      <ProviderProbeResults
        presets={presets}
        probeResults={probeResults}
        probing={probing}
        onAddPreset={handleAddPreset}
      />

      {/* Manual cloud provider add */}
      <ProviderAddForm
        presets={presets}
        onAdd={handleAddCloud}
        onTest={testProviderConnection}
      />

      {/* Configured providers */}
      {providerEntries.length > 0 && (
        <SectionCard title="Configured Providers" icon={Server}>
          <div className="space-y-2">
            {providerEntries.map(([name, config]) => (
              <div key={name} className="flex items-center justify-between rounded-md border border-border p-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">{name}</span>
                  <span className="text-xs text-muted-foreground">{config.driver}</span>
                  <span className="text-xs text-muted-foreground">{config.models.length} models</span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge
                    status={config.has_api_key ? 'idle' : 'error'}
                    label
                  />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Validation messages */}
      {!validation.valid && validation.errors.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {validation.errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
