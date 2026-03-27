import fc from 'fast-check'
import {
  estimateMonthlyCost,
  estimateTemplateCost,
} from '@/utils/cost-estimator'
import type { ProviderModelConfig } from '@/api/types'

const tierArb = fc.constantFrom('large', 'medium', 'small')

const agentArb = fc.record({
  model_provider: fc.string({ minLength: 1, maxLength: 20 }),
  model_id: fc.string({ minLength: 1, maxLength: 20 }),
  tier: tierArb,
})

const modelArb = fc.record({
  id: fc.string({ minLength: 1, maxLength: 20 }),
  alias: fc.constant(null),
  cost_per_1k_input: fc.double({ min: 0.0001, max: 1, noNaN: true }),
  cost_per_1k_output: fc.double({ min: 0.0001, max: 5, noNaN: true }),
  max_context: fc.integer({ min: 1000, max: 1_000_000 }),
  estimated_latency_ms: fc.constant(null),
}) as fc.Arbitrary<ProviderModelConfig>

describe('cost-estimator property tests', () => {
  it('monthly cost is always non-negative', () => {
    fc.assert(
      fc.property(
        fc.array(agentArb, { maxLength: 20 }),
        fc.array(modelArb, { maxLength: 10 }),
        (agents, models) => {
          const result = estimateMonthlyCost(agents, models)
          expect(result.monthlyTotal).toBeGreaterThanOrEqual(0)
        },
      ),
    )
  })

  it('per-agent costs sum to monthly total', () => {
    fc.assert(
      fc.property(
        fc.array(agentArb, { minLength: 1, maxLength: 10 }),
        fc.array(modelArb, { maxLength: 5 }),
        (agents, models) => {
          const result = estimateMonthlyCost(agents, models)
          const sum = result.perAgentBreakdown.reduce((acc, b) => acc + b.monthlyCost, 0)
          expect(result.monthlyTotal).toBeCloseTo(sum, 5)
        },
      ),
    )
  })

  it('breakdown length equals agent count', () => {
    fc.assert(
      fc.property(
        fc.array(agentArb, { maxLength: 20 }),
        fc.array(modelArb, { maxLength: 10 }),
        (agents, models) => {
          const result = estimateMonthlyCost(agents, models)
          expect(result.perAgentBreakdown).toHaveLength(agents.length)
        },
      ),
    )
  })

  it('more agents always means equal or higher total cost', () => {
    fc.assert(
      fc.property(
        fc.array(agentArb, { minLength: 1, maxLength: 10 }),
        agentArb,
        fc.array(modelArb, { maxLength: 5 }),
        (agents, extraAgent, models) => {
          const fewer = estimateMonthlyCost(agents, models)
          const more = estimateMonthlyCost([...agents, extraAgent], models)
          expect(more.monthlyTotal).toBeGreaterThanOrEqual(fewer.monthlyTotal)
        },
      ),
    )
  })

  it('template cost scales linearly with count', () => {
    fc.assert(
      fc.property(
        tierArb,
        fc.integer({ min: 1, max: 50 }),
        (tier, count) => {
          const single = estimateTemplateCost([{ tier, count: 1 }])
          const multi = estimateTemplateCost([{ tier, count }])
          expect(multi).toBeCloseTo(single * count, 5)
        },
      ),
    )
  })

  it('template cost is always non-negative', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            tier: tierArb,
            count: fc.integer({ min: 0, max: 100 }),
          }),
          { maxLength: 10 },
        ),
        (tiers) => {
          expect(estimateTemplateCost(tiers)).toBeGreaterThanOrEqual(0)
        },
      ),
    )
  })

  it('higher input/output ratio shifts cost toward input pricing', () => {
    fc.assert(
      fc.property(agentArb, (agent) => {
        // Use a model where input is cheaper than output (common case)
        const models = [{
          id: agent.model_id,
          alias: null,
          cost_per_1k_input: 0.001,
          cost_per_1k_output: 0.01,
          max_context: 128_000,
          estimated_latency_ms: null,
        } satisfies ProviderModelConfig]

        const highInput = estimateMonthlyCost([agent], models, { inputOutputRatio: 0.9 })
        const lowInput = estimateMonthlyCost([agent], models, { inputOutputRatio: 0.1 })

        // More input (cheaper) means lower total cost when input < output pricing
        expect(highInput.monthlyTotal).toBeLessThanOrEqual(lowInput.monthlyTotal + 0.001)
      }),
    )
  })
})
