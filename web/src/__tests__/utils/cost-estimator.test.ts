import {
  estimateMonthlyCost,
  estimateTemplateCost,
  DEFAULT_DAILY_TOKENS_PER_AGENT,
  DEFAULT_INPUT_OUTPUT_RATIO,
  TIER_FALLBACK_COSTS,
} from '@/utils/cost-estimator'
import type { ProviderModelConfig } from '@/api/types'

const makeModel = (
  overrides: Partial<ProviderModelConfig> = {},
): ProviderModelConfig => ({
  id: 'test-model-001',
  alias: null,
  cost_per_1k_input: 0.003,
  cost_per_1k_output: 0.015,
  max_context: 128_000,
  estimated_latency_ms: null,
  ...overrides,
})

describe('estimateMonthlyCost', () => {
  it('returns zero for empty agent list', () => {
    const result = estimateMonthlyCost([], [])
    expect(result.monthlyTotal).toBe(0)
    expect(result.perAgentBreakdown).toHaveLength(0)
  })

  it('calculates cost for a single agent with known model', () => {
    const agents = [
      { model_provider: 'test-provider', model_id: 'test-model-001', tier: 'medium' },
    ]
    const models = [makeModel()]
    const result = estimateMonthlyCost(agents, models)

    // Daily: 50k tokens. 70% input = 35k, 30% output = 15k
    // Input cost: (35000/1000) * 0.003 = 0.105
    // Output cost: (15000/1000) * 0.015 = 0.225
    // Daily total: 0.33, Monthly: 0.33 * 30 = 9.9
    expect(result.monthlyTotal).toBeCloseTo(9.9, 1)
    expect(result.perAgentBreakdown).toHaveLength(1)
    expect(result.perAgentBreakdown[0]!.agentIndex).toBe(0)
    expect(result.perAgentBreakdown[0]!.modelId).toBe('test-model-001')
    expect(result.perAgentBreakdown[0]!.monthlyCost).toBeCloseTo(9.9, 1)
  })

  it('calculates cost for multiple agents', () => {
    const agents = [
      { model_provider: 'p', model_id: 'large-001', tier: 'large' },
      { model_provider: 'p', model_id: 'small-001', tier: 'small' },
    ]
    const models = [
      makeModel({ id: 'large-001', cost_per_1k_input: 0.015, cost_per_1k_output: 0.075 }),
      makeModel({ id: 'small-001', cost_per_1k_input: 0.0005, cost_per_1k_output: 0.0025 }),
    ]
    const result = estimateMonthlyCost(agents, models)

    expect(result.perAgentBreakdown).toHaveLength(2)
    expect(result.monthlyTotal).toBeCloseTo(
      result.perAgentBreakdown[0]!.monthlyCost + result.perAgentBreakdown[1]!.monthlyCost,
      5,
    )
  })

  it('uses tier fallback when model is not found', () => {
    const agents = [
      { model_provider: 'p', model_id: 'unknown-model', tier: 'large' },
    ]
    const result = estimateMonthlyCost(agents, [])

    const fallback = TIER_FALLBACK_COSTS.large!
    const dailyInput = (DEFAULT_DAILY_TOKENS_PER_AGENT * DEFAULT_INPUT_OUTPUT_RATIO / 1000) * fallback.input
    const dailyOutput = (DEFAULT_DAILY_TOKENS_PER_AGENT * (1 - DEFAULT_INPUT_OUTPUT_RATIO) / 1000) * fallback.output
    const expected = (dailyInput + dailyOutput) * 30

    expect(result.monthlyTotal).toBeCloseTo(expected, 2)
  })

  it('uses medium tier fallback for unknown tier strings', () => {
    const agents = [
      { model_provider: 'p', model_id: 'x', tier: 'unknown-tier' },
    ]
    const resultUnknown = estimateMonthlyCost(agents, [])

    const agentsMedium = [
      { model_provider: 'p', model_id: 'x', tier: 'medium' },
    ]
    const resultMedium = estimateMonthlyCost(agentsMedium, [])

    expect(resultUnknown.monthlyTotal).toBeCloseTo(resultMedium.monthlyTotal, 5)
  })

  it('accepts custom daily tokens and input/output ratio', () => {
    const agents = [
      { model_provider: 'p', model_id: 'test-model-001', tier: 'medium' },
    ]
    const models = [makeModel()]
    const result = estimateMonthlyCost(agents, models, {
      dailyTokensPerAgent: 100_000,
      inputOutputRatio: 0.5,
    })

    // 100k tokens. 50% input = 50k, 50% output = 50k
    // Input: (50000/1000) * 0.003 = 0.15
    // Output: (50000/1000) * 0.015 = 0.75
    // Daily: 0.9, Monthly: 27
    expect(result.monthlyTotal).toBeCloseTo(27, 1)
  })

  it('sets usedFallback to false when all models found', () => {
    const agents = [
      { model_provider: 'p', model_id: 'test-model-001', tier: 'medium' },
    ]
    const models = [makeModel()]
    const result = estimateMonthlyCost(agents, models)
    expect(result.usedFallback).toBe(false)
  })

  it('sets usedFallback to true when model not found', () => {
    const agents = [
      { model_provider: 'p', model_id: 'unknown', tier: 'large' },
    ]
    const result = estimateMonthlyCost(agents, [])
    expect(result.usedFallback).toBe(true)
  })

  it('usedFallback is false for empty agents', () => {
    const result = estimateMonthlyCost([], [])
    expect(result.usedFallback).toBe(false)
  })

  it('includes assumptions in result', () => {
    const result = estimateMonthlyCost([], [])
    expect(result.assumptions).toEqual({
      dailyTokensPerAgent: DEFAULT_DAILY_TOKENS_PER_AGENT,
      inputOutputRatio: DEFAULT_INPUT_OUTPUT_RATIO,
      daysPerMonth: 30,
    })
  })

  it('includes custom assumptions when provided', () => {
    const result = estimateMonthlyCost([], [], {
      dailyTokensPerAgent: 80_000,
      inputOutputRatio: 0.6,
    })
    expect(result.assumptions.dailyTokensPerAgent).toBe(80_000)
    expect(result.assumptions.inputOutputRatio).toBe(0.6)
  })
})

describe('estimateTemplateCost', () => {
  it('estimates cost from agent count and tiers', () => {
    const result = estimateTemplateCost([
      { tier: 'large', count: 2 },
      { tier: 'medium', count: 2 },
      { tier: 'small', count: 1 },
    ])
    expect(result).toBeGreaterThan(0)
    expect(Number.isFinite(result)).toBe(true)
  })

  it('returns zero for empty tier list', () => {
    expect(estimateTemplateCost([])).toBe(0)
  })

  it('scales linearly with count', () => {
    const single = estimateTemplateCost([{ tier: 'medium', count: 1 }])
    const triple = estimateTemplateCost([{ tier: 'medium', count: 3 }])
    expect(triple).toBeCloseTo(single * 3, 5)
  })

  it('large tier costs more than medium costs more than small', () => {
    const large = estimateTemplateCost([{ tier: 'large', count: 1 }])
    const medium = estimateTemplateCost([{ tier: 'medium', count: 1 }])
    const small = estimateTemplateCost([{ tier: 'small', count: 1 }])
    expect(large).toBeGreaterThan(medium)
    expect(medium).toBeGreaterThan(small)
  })
})

describe('TIER_FALLBACK_COSTS', () => {
  it('has entries for large, medium, and small', () => {
    expect(TIER_FALLBACK_COSTS).toHaveProperty('large')
    expect(TIER_FALLBACK_COSTS).toHaveProperty('medium')
    expect(TIER_FALLBACK_COSTS).toHaveProperty('small')
  })

  it('all costs are positive', () => {
    for (const tier of Object.values(TIER_FALLBACK_COSTS)) {
      expect(tier.input).toBeGreaterThan(0)
      expect(tier.output).toBeGreaterThan(0)
    }
  })
})
