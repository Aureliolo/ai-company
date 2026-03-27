/** Cost estimation for the setup wizard. */

import type { ProviderModelConfig } from '@/api/types'

/** Default daily token consumption per agent. */
export const DEFAULT_DAILY_TOKENS_PER_AGENT = 50_000

/** Default ratio of input tokens to total tokens (0-1). */
export const DEFAULT_INPUT_OUTPUT_RATIO = 0.7

/** Days per month used in cost projection. */
const DAYS_PER_MONTH = 30

interface TierCost {
  readonly input: number
  readonly output: number
}

/** Fallback cost per 1K tokens when a model is not found in provider data. */
export const TIER_FALLBACK_COSTS: Readonly<Record<string, TierCost>> = {
  large: { input: 0.015, output: 0.075 },
  medium: { input: 0.003, output: 0.015 },
  small: { input: 0.0005, output: 0.0025 },
}

const DEFAULT_TIER_COST: TierCost = { input: 0.003, output: 0.015 }

/** Get fallback costs for a tier, defaulting to medium if tier is unknown. */
function getTierCosts(tier: string): TierCost {
  return TIER_FALLBACK_COSTS[tier] ?? DEFAULT_TIER_COST
}

interface CostEstimateOptions {
  readonly dailyTokensPerAgent?: number
  readonly inputOutputRatio?: number
}

interface AgentCostBreakdown {
  readonly agentIndex: number
  readonly modelId: string
  readonly monthlyCost: number
}

export interface CostEstimate {
  readonly monthlyTotal: number
  readonly perAgentBreakdown: readonly AgentCostBreakdown[]
  /** True when one or more agents used tier-based fallback costs instead of actual model pricing. */
  readonly usedFallback: boolean
  readonly assumptions: {
    readonly dailyTokensPerAgent: number
    readonly inputOutputRatio: number
    readonly daysPerMonth: number
  }
}

interface AgentCostInput {
  readonly model_provider: string
  readonly model_id: string
  readonly tier: string
}

/**
 * Estimate monthly cost for a set of agents based on their model assignments.
 *
 * Looks up each agent's model in the provided model list. Falls back to
 * tier-based heuristics when a model is not found.
 */
export function estimateMonthlyCost(
  agents: readonly AgentCostInput[],
  models: readonly ProviderModelConfig[],
  options?: CostEstimateOptions,
): CostEstimate {
  const dailyTokens = options?.dailyTokensPerAgent ?? DEFAULT_DAILY_TOKENS_PER_AGENT
  const inputRatio = options?.inputOutputRatio ?? DEFAULT_INPUT_OUTPUT_RATIO

  const modelMap = new Map<string, ProviderModelConfig>()
  for (const model of models) {
    modelMap.set(model.id, model)
  }

  const breakdown: AgentCostBreakdown[] = []
  let usedFallback = false

  for (let i = 0; i < agents.length; i++) {
    const agent = agents[i]!
    const model = modelMap.get(agent.model_id)

    let inputCostPer1k: number
    let outputCostPer1k: number

    if (model) {
      inputCostPer1k = model.cost_per_1k_input
      outputCostPer1k = model.cost_per_1k_output
    } else {
      usedFallback = true
      const fallback = getTierCosts(agent.tier)
      inputCostPer1k = fallback.input
      outputCostPer1k = fallback.output
    }

    const dailyInputTokens = dailyTokens * inputRatio
    const dailyOutputTokens = dailyTokens * (1 - inputRatio)
    const dailyCost =
      (dailyInputTokens / 1000) * inputCostPer1k +
      (dailyOutputTokens / 1000) * outputCostPer1k

    breakdown.push({
      agentIndex: i,
      modelId: agent.model_id,
      monthlyCost: dailyCost * DAYS_PER_MONTH,
    })
  }

  const monthlyTotal = breakdown.reduce((sum, b) => sum + b.monthlyCost, 0)

  return {
    monthlyTotal,
    perAgentBreakdown: breakdown,
    usedFallback,
    assumptions: {
      dailyTokensPerAgent: dailyTokens,
      inputOutputRatio: inputRatio,
      daysPerMonth: DAYS_PER_MONTH,
    },
  }
}

interface TierCount {
  readonly tier: string
  readonly count: number
}

/**
 * Estimate monthly cost from template-level tier counts (before agents exist).
 *
 * Uses tier fallback costs since no specific models are assigned yet.
 */
export function estimateTemplateCost(tiers: readonly TierCount[]): number {
  let total = 0
  for (const { tier, count } of tiers) {
    const fallback = getTierCosts(tier)
    const dailyInputTokens = DEFAULT_DAILY_TOKENS_PER_AGENT * DEFAULT_INPUT_OUTPUT_RATIO
    const dailyOutputTokens = DEFAULT_DAILY_TOKENS_PER_AGENT * (1 - DEFAULT_INPUT_OUTPUT_RATIO)
    const dailyCostPerAgent =
      (dailyInputTokens / 1000) * fallback.input +
      (dailyOutputTokens / 1000) * fallback.output
    total += dailyCostPerAgent * DAYS_PER_MONTH * count
  }
  return total
}
