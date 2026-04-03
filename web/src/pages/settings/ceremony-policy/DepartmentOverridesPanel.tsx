import { useCallback, useEffect, useState } from 'react'
import { Building2, ChevronDown, ChevronRight } from 'lucide-react'
import type { CeremonyPolicyConfig, CeremonyStrategyType, Department } from '@/api/types'
import { InheritToggle } from '@/components/ui/inherit-toggle'
import { SectionCard } from '@/components/ui/section-card'
import { useCeremonyPolicyStore } from '@/stores/ceremony-policy'
import { CEREMONY_STRATEGY_LABELS } from '@/utils/constants'
import { cn } from '@/lib/utils'
import { StrategyPicker } from './StrategyPicker'
import { PolicyFieldsPanel } from './PolicyFieldsPanel'

export interface DepartmentOverridesPanelProps {
  departments: readonly Department[]
}

function DepartmentRow({ dept }: { dept: Department }) {
  const [expanded, setExpanded] = useState(false)
  const policy = useCeremonyPolicyStore((s) => s.departmentPolicies.get(dept.name))
  const fetchPolicy = useCeremonyPolicyStore((s) => s.fetchDepartmentPolicy)
  const updatePolicy = useCeremonyPolicyStore((s) => s.updateDepartmentPolicy)
  const clearPolicy = useCeremonyPolicyStore((s) => s.clearDepartmentPolicy)
  const saving = useCeremonyPolicyStore((s) => s.saving)

  useEffect(() => {
    fetchPolicy(dept.name)
  }, [dept.name, fetchPolicy])

  const hasOverride = policy != null && Object.keys(policy).length > 0
  const strategy = policy?.strategy ?? 'task_driven'

  const handleInheritChange = useCallback(
    (inherit: boolean) => {
      if (inherit) {
        clearPolicy(dept.name)
      } else {
        updatePolicy(dept.name, { strategy: 'task_driven' })
      }
    },
    [dept.name, clearPolicy, updatePolicy],
  )

  const handleStrategyChange = useCallback(
    (s: CeremonyStrategyType) => {
      updatePolicy(dept.name, { ...policy, strategy: s, strategy_config: {} })
    },
    [dept.name, policy, updatePolicy],
  )

  const handlePolicyFieldChange = useCallback(
    (field: keyof CeremonyPolicyConfig, value: unknown) => {
      updatePolicy(dept.name, { ...policy, [field]: value })
    },
    [dept.name, policy, updatePolicy],
  )

  const Chevron = expanded ? ChevronDown : ChevronRight

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-card/50"
      >
        <Chevron className="size-3.5 text-text-muted" />
        <span className="flex-1 text-sm font-medium">{dept.display_name ?? dept.name}</span>
        <span className="text-xs text-text-muted">
          {hasOverride
            ? CEREMONY_STRATEGY_LABELS[strategy as CeremonyStrategyType]
            : 'Inherit'}
        </span>
      </button>

      {expanded && (
        <div className="space-y-3 px-3 pb-3">
          <InheritToggle
            inherit={!hasOverride}
            onChange={handleInheritChange}
            disabled={saving}
          />

          {hasOverride && (
            <div className={cn('space-y-3 pl-2 border-l-2 border-accent/20')}>
              <StrategyPicker
                value={strategy as CeremonyStrategyType}
                onChange={handleStrategyChange}
                disabled={saving}
              />
              <PolicyFieldsPanel
                velocityCalculator={policy?.velocity_calculator ?? 'task_driven'}
                autoTransition={policy?.auto_transition ?? true}
                transitionThreshold={policy?.transition_threshold ?? 1.0}
                onVelocityCalculatorChange={(v) => handlePolicyFieldChange('velocity_calculator', v)}
                onAutoTransitionChange={(v) => handlePolicyFieldChange('auto_transition', v)}
                onTransitionThresholdChange={(v) => handlePolicyFieldChange('transition_threshold', v)}
                disabled={saving}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function DepartmentOverridesPanel({ departments }: DepartmentOverridesPanelProps) {
  if (departments.length === 0) {
    return (
      <p className="text-xs text-text-secondary">
        No departments configured. Department overrides will appear here once departments are added.
      </p>
    )
  }

  return (
    <SectionCard title="Department Overrides" icon={Building2}>
      <div className="divide-y divide-border rounded-md border border-border">
        {departments.map((dept) => (
          <DepartmentRow key={dept.name} dept={dept} />
        ))}
      </div>
    </SectionCard>
  )
}
