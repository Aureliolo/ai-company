import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, Loader2, Settings, Timer } from 'lucide-react'
import type { CeremonyStrategyType, Department, VelocityCalcType } from '@/api/types'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SectionCard } from '@/components/ui/section-card'
import { PolicySourceBadge } from '@/components/ui/policy-source-badge'
import { useSettingsStore } from '@/stores/settings'
import { useCeremonyPolicyStore } from '@/stores/ceremony-policy'
import { useToastStore } from '@/stores/toast'
import { ROUTES } from '@/router/routes'
import { STRATEGY_DEFAULT_VELOCITY_CALC } from '@/utils/constants'
import { StrategyPicker } from './StrategyPicker'
import { StrategyChangeWarning } from './StrategyChangeWarning'
import { StrategyConfigPanel } from './StrategyConfigPanel'
import { PolicyFieldsPanel } from './PolicyFieldsPanel'
import { DepartmentOverridesPanel } from './DepartmentOverridesPanel'

export default function CeremonyPolicyPage() {
  const addToast = useToastStore((s) => s.add)
  const settingsEntries = useSettingsStore((s) => s.entries)
  const updateSetting = useSettingsStore((s) => s.updateSetting)

  const resolvedPolicy = useCeremonyPolicyStore((s) => s.resolvedPolicy)
  const activeStrategy = useCeremonyPolicyStore((s) => s.activeStrategy)
  const loading = useCeremonyPolicyStore((s) => s.loading)
  const fetchResolvedPolicy = useCeremonyPolicyStore((s) => s.fetchResolvedPolicy)
  const fetchActiveStrategy = useCeremonyPolicyStore((s) => s.fetchActiveStrategy)

  // Derive initial values from settings entries
  const settingsSnapshot = useMemo(() => {
    const get = (key: string) => settingsEntries.find(
      (e) => e.definition.namespace === 'coordination' && e.definition.key === key,
    )?.value

    let config: Record<string, unknown> = {}
    const sc = get('ceremony_strategy_config')
    if (sc) {
      try { config = JSON.parse(sc) as Record<string, unknown> } catch { /* keep default */ }
    }

    return {
      strategy: (get('ceremony_strategy') as CeremonyStrategyType | undefined) ?? 'task_driven' as CeremonyStrategyType,
      strategyConfig: config,
      velocityCalculator: (get('ceremony_velocity_calculator') as VelocityCalcType | undefined) ?? 'task_driven' as VelocityCalcType,
      autoTransition: get('ceremony_auto_transition') !== 'false',
      transitionThreshold: Number(get('ceremony_transition_threshold') ?? '1.0'),
    }
  }, [settingsEntries])

  // Local form state for project-level policy (initialized from settings)
  const [strategy, setStrategy] = useState<CeremonyStrategyType>(settingsSnapshot.strategy)
  const [strategyConfig, setStrategyConfig] = useState<Record<string, unknown>>(settingsSnapshot.strategyConfig)
  const [velocityCalculator, setVelocityCalculator] = useState<VelocityCalcType>(settingsSnapshot.velocityCalculator)
  const [autoTransition, setAutoTransition] = useState(settingsSnapshot.autoTransition)
  const [transitionThreshold, setTransitionThreshold] = useState(settingsSnapshot.transitionThreshold)
  const [saving, setSaving] = useState(false)

  // Departments for the overrides panel
  const [departments, setDepartments] = useState<readonly Department[]>([])

  // Fetch resolved policy and active strategy on mount
  useEffect(() => {
    fetchResolvedPolicy()
    fetchActiveStrategy()
  }, [fetchResolvedPolicy, fetchActiveStrategy])

  // Fetch departments
  useEffect(() => {
    import('@/api/endpoints/company').then(({ listDepartments }) =>
      listDepartments().then((result) => setDepartments(result.data)),
    )
  }, [])

  // Save handler: persist all ceremony settings
  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      await Promise.all([
        updateSetting('coordination', 'ceremony_strategy', strategy),
        updateSetting('coordination', 'ceremony_strategy_config', JSON.stringify(strategyConfig)),
        updateSetting('coordination', 'ceremony_velocity_calculator', velocityCalculator),
        updateSetting('coordination', 'ceremony_auto_transition', String(autoTransition)),
        updateSetting('coordination', 'ceremony_transition_threshold', String(transitionThreshold)),
      ])
      addToast({ variant: 'success', title: 'Ceremony policy saved' })
      fetchResolvedPolicy()
    } catch {
      addToast({ variant: 'error', title: 'Failed to save ceremony policy' })
    } finally {
      setSaving(false)
    }
  }, [
    strategy, strategyConfig, velocityCalculator, autoTransition, transitionThreshold,
    updateSetting, addToast, fetchResolvedPolicy,
  ])

  // When strategy changes, update velocity calculator to the strategy default
  const handleStrategyChange = useCallback((s: CeremonyStrategyType) => {
    setStrategy(s)
    setVelocityCalculator(STRATEGY_DEFAULT_VELOCITY_CALC[s])
    setStrategyConfig({})
  }, [])

  return (
    <ErrorBoundary level="page">
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Link
            to={ROUTES.SETTINGS}
            className="rounded-md p-1.5 text-text-muted transition-colors hover:bg-card hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <div className="flex items-center gap-2">
            <Timer className="size-5 text-accent" />
            <h1 className="text-lg font-semibold">Ceremony Policy</h1>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-6 animate-spin text-text-muted" />
          </div>
        )}

        {!loading && (
          <>
            {/* Strategy change warning */}
            {activeStrategy?.strategy && strategy !== activeStrategy.strategy && (
              <StrategyChangeWarning
                currentStrategy={strategy}
                activeStrategy={activeStrategy.strategy}
              />
            )}

            {/* Project-level policy */}
            <SectionCard title="Project Policy" icon={Settings}>
              <div className="space-y-5">
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <StrategyPicker
                      value={strategy}
                      onChange={handleStrategyChange}
                    />
                  </div>
                  {resolvedPolicy && (
                    <PolicySourceBadge source={resolvedPolicy.strategy.source} className="mt-7" />
                  )}
                </div>

                <div className="border-t border-border pt-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                    Strategy Configuration
                  </p>
                  <StrategyConfigPanel
                    strategy={strategy}
                    config={strategyConfig}
                    onChange={setStrategyConfig}
                  />
                </div>

                <div className="border-t border-border pt-4">
                  <PolicyFieldsPanel
                    velocityCalculator={velocityCalculator}
                    autoTransition={autoTransition}
                    transitionThreshold={transitionThreshold}
                    onVelocityCalculatorChange={setVelocityCalculator}
                    onAutoTransitionChange={setAutoTransition}
                    onTransitionThresholdChange={setTransitionThreshold}
                    resolvedPolicy={resolvedPolicy}
                  />
                </div>

                <div className="flex justify-end pt-2">
                  <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
                    Save Policy
                  </Button>
                </div>
              </div>
            </SectionCard>

            {/* Department overrides */}
            <DepartmentOverridesPanel departments={departments} />
          </>
        )}
      </div>
    </ErrorBoundary>
  )
}
