/** Sprint ceremony strategy, velocity and policy field resolution types. */

export type CeremonyStrategyType =
  | 'task_driven'
  | 'calendar'
  | 'hybrid'
  | 'event_driven'
  | 'budget_driven'
  | 'throughput_adaptive'
  | 'external_trigger'
  | 'milestone_driven'

export type VelocityCalcType =
  | 'task_driven'
  | 'calendar'
  | 'multi_dimensional'
  | 'budget'
  | 'points_per_sprint'

export interface CeremonyPolicyConfig {
  strategy?: CeremonyStrategyType | null
  strategy_config?: Record<string, unknown> | null
  velocity_calculator?: VelocityCalcType | null
  auto_transition?: boolean | null
  transition_threshold?: number | null
}

export type PolicyFieldSource = 'project' | 'department' | 'default'

export interface ResolvedPolicyField<T = unknown> {
  value: T
  source: PolicyFieldSource
}

export interface ResolvedCeremonyPolicyResponse {
  readonly strategy: ResolvedPolicyField<CeremonyStrategyType>
  readonly strategy_config: ResolvedPolicyField<Record<string, unknown>>
  readonly velocity_calculator: ResolvedPolicyField<VelocityCalcType>
  readonly auto_transition: ResolvedPolicyField<boolean>
  readonly transition_threshold: ResolvedPolicyField<number>
}

export type ActiveCeremonyStrategy =
  | { readonly strategy: CeremonyStrategyType; readonly sprint_id: string }
  | { readonly strategy: null; readonly sprint_id: null }
