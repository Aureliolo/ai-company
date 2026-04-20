import type { CeremonyStrategyType } from '@/api/types/ceremony-policy'
import { TaskDrivenConfig } from './strategies/TaskDrivenConfig'
import { CalendarConfig } from './strategies/CalendarConfig'
import { HybridConfig } from './strategies/HybridConfig'
import { EventDrivenConfig } from './strategies/EventDrivenConfig'
import { BudgetDrivenConfig } from './strategies/BudgetDrivenConfig'
import { ThroughputAdaptiveConfig } from './strategies/ThroughputAdaptiveConfig'
import { ExternalTriggerConfig } from './strategies/ExternalTriggerConfig'
import { MilestoneDrivenConfig } from './strategies/MilestoneDrivenConfig'

function assertNever(value: never): never {
  throw new Error(`Unhandled strategy: ${String(value)}`)
}

export interface StrategyConfigPanelProps {
  strategy: CeremonyStrategyType
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function StrategyConfigPanel({
  strategy,
  config,
  onChange,
  disabled,
}: StrategyConfigPanelProps) {
  switch (strategy) {
    case 'task_driven':
      return <TaskDrivenConfig config={config} onChange={onChange} disabled={disabled} />
    case 'calendar':
      return <CalendarConfig config={config} onChange={onChange} disabled={disabled} />
    case 'hybrid':
      return <HybridConfig config={config} onChange={onChange} disabled={disabled} />
    case 'event_driven':
      return <EventDrivenConfig config={config} onChange={onChange} disabled={disabled} />
    case 'budget_driven':
      return <BudgetDrivenConfig config={config} onChange={onChange} disabled={disabled} />
    case 'throughput_adaptive':
      return <ThroughputAdaptiveConfig config={config} onChange={onChange} disabled={disabled} />
    case 'external_trigger':
      return <ExternalTriggerConfig config={config} onChange={onChange} disabled={disabled} />
    case 'milestone_driven':
      return <MilestoneDrivenConfig config={config} onChange={onChange} disabled={disabled} />
    default:
      return assertNever(strategy)
  }
}
