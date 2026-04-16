import type { Meta, StoryObj } from '@storybook/react'

import type { ABTestSummary } from '@/api/endpoints/meta'
import { MetaABTestView } from './MetaABTestView'

const meta = {
  title: 'Pages/Meta/ABTestView',
  component: MetaABTestView,
  parameters: { a11y: { test: 'error' } },
} satisfies Meta<typeof MetaABTestView>

export default meta
type Story = StoryObj<typeof meta>

const controlMetrics = {
  group: 'control' as const,
  agent_count: 10,
  observation_count: 20,
  avg_quality_score: 7.5,
  avg_success_rate: 0.85,
  total_spend: 100.0,
}

const treatmentMetrics = {
  group: 'treatment' as const,
  agent_count: 10,
  observation_count: 20,
  avg_quality_score: 8.2,
  avg_success_rate: 0.91,
  total_spend: 95.0,
}

const baseTest: ABTestSummary = {
  proposal_id: '550e8400-e29b-41d4-a716-446655440000',
  proposal_title: 'Increase collaboration threshold',
  control_metrics: controlMetrics,
  treatment_metrics: treatmentMetrics,
  verdict: null,
  observation_hours_elapsed: 24,
  observation_hours_total: 48,
}

/** No active A/B tests. */
export const Empty: Story = {
  args: { tests: [] },
}

/** Active test in progress (no verdict yet). */
export const ActiveTest: Story = {
  args: { tests: [baseTest] },
}

/** Treatment declared winner. */
export const TreatmentWins: Story = {
  args: {
    tests: [{ ...baseTest, verdict: 'treatment_wins', observation_hours_elapsed: 48 }],
  },
}

/** Inconclusive result. */
export const Inconclusive: Story = {
  args: {
    tests: [{ ...baseTest, verdict: 'inconclusive', observation_hours_elapsed: 48 }],
  },
}

/** Treatment regressed. */
export const TreatmentRegressed: Story = {
  args: {
    tests: [
      {
        ...baseTest,
        verdict: 'treatment_regressed',
        observation_hours_elapsed: 12,
        treatment_metrics: {
          ...treatmentMetrics,
          avg_quality_score: 5.0,
          avg_success_rate: 0.65,
        },
      },
    ],
  },
}
