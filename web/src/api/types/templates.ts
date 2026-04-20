/** Template pack discovery and application types. */

export interface PackInfoResponse {
  readonly name: string
  readonly display_name: string
  readonly description: string
  readonly source: 'builtin' | 'user'
  readonly tags: readonly string[]
  readonly agent_count: number
  readonly department_count: number
}

export type RebalanceMode = 'none' | 'scale_existing' | 'reject_if_over'

export interface ApplyTemplatePackRequest {
  readonly pack_name: string
  readonly rebalance_mode?: RebalanceMode
}

export interface ApplyTemplatePackResponse {
  readonly pack_name: string
  readonly agents_added: number
  readonly departments_added: number
  readonly budget_before: number
  readonly budget_after: number
  readonly rebalance_mode: RebalanceMode
  readonly scale_factor: number | null
}
