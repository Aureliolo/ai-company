import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateProvidersStep } from '@/utils/setup-validation'
import { getProviderStatus } from '@/utils/provider-status'
import type { ProviderConfig } from '@/api/types'
import { ProviderProbeResults } from './ProviderProbeResults'
import { ProviderAddForm } from './ProviderAddForm'
import { Server } from 'lucide-react'

interface ProviderRowProps {
  name: string
  config: ProviderConfig
}

function ProviderRow({ name, config }: ProviderRowProps) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border p-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-foreground">{name}</span>
        <span className="text-xs text-muted-foreground">{config.driver}</span>
        <span className="text-xs text-muted-foreground">{config.models.length} models</span>
      </div>
      <div className="flex items-center gap-2">
        <StatusBadge status={getProviderStatus(config)} label />
      </div>
    </div>
  )
}

export function ProvidersStep() {
  const agents = useSetupWizardStore((s) => s.agents)
  const providers = useSetupWizardStore((s) => s.providers)
  const presets = useSetupWizardStore((s) => s.presets)
  const probeResults = useSetupWizardStore((s) => s.probeResults)
  const probing = useSetupWizardStore((s) => s.probing)
  const providersLoading = useSetupWizardStore((s) => s.providersLoading)
  const providersError = useSetupWizardStore((s) => s.providersError)
  const presetsLoading = useSetupWizardStore((s) => s.presetsLoading)
  const presetsError = useSetupWizardStore((s) => s.presetsError)

  const fetchProviders = useSetupWizardStore((s) => s.fetchProviders)
  const fetchPresets = useSetupWizardStore((s) => s.fetchPresets)
  const probeAllPresets = useSetupWizardStore((s) => s.probeAllPresets)
  const createProviderFromPreset = useSetupWizardStore((s) => s.createProviderFromPreset)
  const testProviderConnection = useSetupWizardStore((s) => s.testProviderConnection)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  const providersCount = Object.keys(providers).length
  const probeResultsCount = Object.keys(probeResults).length
  const probeAttempted = useRef(false)

  // Fetch providers on mount
  useEffect(() => {
    if (providersCount === 0 && !providersLoading && !providersError) {
      fetchProviders()
    }
  }, [providersCount, providersLoading, providersError, fetchProviders])

  // Fetch presets on mount
  useEffect(() => {
    if (presets.length === 0 && !presetsLoading && !presetsError) {
      fetchPresets()
    }
  }, [presets.length, presetsLoading, presetsError, fetchPresets])

  // Auto-probe local presets (once per mount)
  useEffect(() => {
    if (presets.length > 0 && probeResultsCount === 0 && !probing && !probeAttempted.current) {
      probeAttempted.current = true
      probeAllPresets()
    }
  }, [presets.length, probeResultsCount, probing, probeAllPresets])

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

      {/* Auto-detect results + Manual cloud provider add */}
      {presetsLoading ? (
        <Skeleton className="h-32 rounded-lg" />
      ) : presetsError && presets.length === 0 ? (
        <div className="space-y-2">
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            Failed to load provider presets: {presetsError}
          </div>
          <Button variant="outline" size="sm" onClick={() => void fetchPresets()}>
            Retry
          </Button>
        </div>
      ) : (
        <>
          <ProviderProbeResults
            presets={presets}
            probeResults={probeResults}
            probing={probing}
            onAddPreset={handleAddPreset}
          />

          <ProviderAddForm
            presets={presets}
            onAdd={handleAddCloud}
            onTest={testProviderConnection}
          />
        </>
      )}

      {/* Configured providers */}
      {providerEntries.length > 0 && (
        <SectionCard title="Configured Providers" icon={Server}>
          <div className="space-y-2">
            {providerEntries.map(([name, config]) => (
              <ProviderRow key={name} name={name} config={config} />
            ))}
          </div>
        </SectionCard>
      )}

      {/* Validation messages */}
      {!validation.valid && validation.errors.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {validation.errors.map((err) => (
            <li key={err}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
