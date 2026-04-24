import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ErrorBanner } from '@/components/ui/error-banner'
import { StatusBadge } from '@/components/ui/status-badge'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateProvidersStep } from '@/utils/setup-validation'
import { getProviderStatus } from '@/utils/provider-status'
import type { ProviderConfig } from '@/api/types/providers'
import { ProviderProbeResults } from './ProviderProbeResults'
import { ProviderFormModal, type ProviderFormOverrides } from '@/pages/providers/ProviderFormModal'
import { Server, Plus } from 'lucide-react'

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
  const probeErrors = useSetupWizardStore((s) => s.probeErrors)
  const probeGlobalError = useSetupWizardStore((s) => s.probeGlobalError)
  const probing = useSetupWizardStore((s) => s.probing)
  const providersLoading = useSetupWizardStore((s) => s.providersLoading)
  const providersError = useSetupWizardStore((s) => s.providersError)
  const presetsLoading = useSetupWizardStore((s) => s.presetsLoading)
  const presetsError = useSetupWizardStore((s) => s.presetsError)

  const fetchProviders = useSetupWizardStore((s) => s.fetchProviders)
  const fetchPresets = useSetupWizardStore((s) => s.fetchPresets)
  const probeAllPresets = useSetupWizardStore((s) => s.probeAllPresets)
  const reprobePresets = useSetupWizardStore((s) => s.reprobePresets)
  const createProviderFromPreset = useSetupWizardStore((s) => s.createProviderFromPreset)
  const createProviderFromPresetFull = useSetupWizardStore((s) => s.createProviderFromPresetFull)
  const createProviderCustom = useSetupWizardStore((s) => s.createProviderCustom)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  const [drawerOpen, setDrawerOpen] = useState(false)

  const probeResultsCount = Object.keys(probeResults).length
  const fetchedRef = useRef(false)

  // Fetch providers and presets once on first mount (not on every re-render)
  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true

    void fetchProviders()
    void fetchPresets()
  }, [fetchProviders, fetchPresets])

  // Auto-probe local presets once after presets are loaded
  const probeAttemptedRef = useRef(false)
  useEffect(() => {
    if (presets.length > 0 && probeResultsCount === 0 && !probing && !probeAttemptedRef.current) {
      probeAttemptedRef.current = true
      void probeAllPresets()
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
    async (presetName: string, detectedUrl?: string) => {
      await createProviderFromPreset(presetName, presetName, undefined, detectedUrl)
      // Only refresh if no error was set (e.g. discovery failure)
      if (!useSetupWizardStore.getState().providersError) {
        await fetchProviders()
      }
    },
    [createProviderFromPreset, fetchProviders],
  )

  const handleReprobe = useCallback(async () => {
    probeAttemptedRef.current = true
    await reprobePresets()
  }, [reprobePresets])

  // Overrides for ProviderFormModal to use setup wizard store
  const drawerOverrides: ProviderFormOverrides = useMemo(() => ({
    presets,
    presetsLoading,
    presetsError,
    onFetchPresets: fetchPresets,
    onCreateFromPreset: async (data) => {
      const result = await createProviderFromPresetFull(data)
      if (result && !useSetupWizardStore.getState().providersError) {
        await fetchProviders()
      }
      return result
    },
    onCreateProvider: async (data) => {
      const result = await createProviderCustom(data)
      if (result && !useSetupWizardStore.getState().providersError) {
        await fetchProviders()
      }
      return result
    },
  }), [presets, presetsLoading, presetsError, fetchPresets, createProviderFromPresetFull, createProviderCustom, fetchProviders])

  if (providersLoading && Object.keys(providers).length === 0) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    )
  }

  const providerEntries = Object.entries(providers)
  // Which providers do agents need?
  const neededProviders = new Set(agents.map((a) => a.model_provider).filter((p): p is string => Boolean(p)))
  const missingProviders = [...neededProviders].filter((p) => !providers[p])

  return (
    <div className="space-y-section-gap">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Set Up Providers</h2>
        <p className="text-sm text-muted-foreground">
          Connect your LLM providers so agents can work.
        </p>
      </div>

      {providersError && (
        <ErrorBanner
          title="Failed to load providers"
          description={providersError}
          onRetry={() => void fetchProviders()}
        />
      )}

      {probeGlobalError && (
        <ErrorBanner
          title="Provider probe did not complete"
          description={`${probeGlobalError} Retry to try again, or skip to configure providers manually below.`}
          onRetry={handleReprobe}
        />
      )}

      {Object.keys(probeErrors).length > 0 && (
        <ErrorBanner
          severity="warning"
          title={`Probe failed for ${Object.keys(probeErrors).length} preset${Object.keys(probeErrors).length === 1 ? '' : 's'}`}
          description={`Ensure the provider is running, then retry. You can also skip the probe and configure it manually using the Add Provider button below. ${Object.entries(probeErrors).map(([name, msg]) => `${name}: ${msg}`).join(' | ')}`}
          onRetry={handleReprobe}
        />
      )}

      {/* Missing provider warnings */}
      {missingProviders.length > 0 && (
        <ErrorBanner
          severity="warning"
          title="Agents need providers that are not configured"
          description={`Missing: ${missingProviders.join(', ')}`}
        />
      )}

      {/* Auto-detect results */}
      {presetsLoading ? (
        <Skeleton className="h-32 rounded-lg" />
      ) : presetsError && presets.length === 0 ? (
        <ErrorBanner
          title="Failed to load provider presets"
          description={presetsError}
          onRetry={() => void fetchPresets()}
        />
      ) : (
        <ProviderProbeResults
          presets={presets}
          probeResults={probeResults}
          probing={probing}
          providers={providers}
          onAddPreset={handleAddPreset}
          onReprobe={handleReprobe}
        />
      )}

      {/* Add Provider button (opens full form drawer) */}
      <Button
        variant="outline"
        size="sm"
        onClick={() => setDrawerOpen(true)}
        className="gap-1.5"
      >
        <Plus className="size-3.5" />
        Add Provider
      </Button>

      <ProviderFormModal
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode="create"
        overrides={drawerOverrides}
      />

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
