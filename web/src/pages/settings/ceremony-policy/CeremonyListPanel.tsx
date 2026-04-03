import { useCallback, useState } from 'react'
import { ChevronDown, ChevronRight, List } from 'lucide-react'
import type { CeremonyPolicyConfig, CeremonyStrategyType } from '@/api/types'
import { InheritToggle } from '@/components/ui/inherit-toggle'
import { SectionCard } from '@/components/ui/section-card'
import { CEREMONY_STRATEGY_LABELS } from '@/utils/constants'
import { cn } from '@/lib/utils'
import { StrategyPicker } from './StrategyPicker'
import { PolicyFieldsPanel } from './PolicyFieldsPanel'

export interface CeremonyOverride {
  name: string
  policy: CeremonyPolicyConfig | null
}

export interface CeremonyListPanelProps {
  /** Per-ceremony overrides keyed by ceremony name. */
  overrides: Readonly<Record<string, CeremonyPolicyConfig | null>>
  /** Known ceremony names from the sprint config. */
  ceremonyNames: readonly string[]
  /** Called when a ceremony override changes. */
  onOverrideChange: (name: string, policy: CeremonyPolicyConfig | null) => void
  saving?: boolean
}

function CeremonyRow({
  name,
  policy,
  onOverrideChange,
  saving,
}: {
  name: string
  policy: CeremonyPolicyConfig | null
  onOverrideChange: (name: string, policy: CeremonyPolicyConfig | null) => void
  saving?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const hasOverride = policy != null && Object.keys(policy).length > 0
  const strategy = policy?.strategy ?? 'task_driven'

  const handleInheritChange = useCallback(
    (inherit: boolean) => {
      if (inherit) {
        onOverrideChange(name, null)
      } else {
        onOverrideChange(name, { strategy: 'task_driven' })
      }
    },
    [name, onOverrideChange],
  )

  const handleStrategyChange = useCallback(
    (s: CeremonyStrategyType) => {
      onOverrideChange(name, { ...policy, strategy: s, strategy_config: {} })
    },
    [name, policy, onOverrideChange],
  )

  const Chevron = expanded ? ChevronDown : ChevronRight

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-card/50"
      >
        <Chevron className="size-3.5 text-text-muted" />
        <span className="flex-1 text-sm font-medium font-mono">{name}</span>
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
            inheritFrom="project/department"
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
                onVelocityCalculatorChange={(v) => onOverrideChange(name, { ...policy, velocity_calculator: v })}
                onAutoTransitionChange={(v) => onOverrideChange(name, { ...policy, auto_transition: v })}
                onTransitionThresholdChange={(v) => onOverrideChange(name, { ...policy, transition_threshold: v })}
                disabled={saving}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function CeremonyListPanel({
  overrides,
  ceremonyNames,
  onOverrideChange,
  saving,
}: CeremonyListPanelProps) {
  if (ceremonyNames.length === 0) {
    return (
      <p className="text-xs text-text-secondary">
        No ceremonies configured in the sprint config.
      </p>
    )
  }

  return (
    <SectionCard title="Per-Ceremony Overrides" icon={List}>
      <p className="mb-3 text-xs text-text-secondary">
        Override the policy for individual ceremonies. Unoverridden ceremonies
        inherit from the department or project level.
      </p>
      <div className="divide-y divide-border rounded-md border border-border">
        {ceremonyNames.map((name) => (
          <CeremonyRow
            key={name}
            name={name}
            policy={overrides[name] ?? null}
            onOverrideChange={onOverrideChange}
            saving={saving}
          />
        ))}
      </div>
    </SectionCard>
  )
}
