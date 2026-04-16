import type { Meta, StoryObj } from '@storybook/react'

import type { ABTestSummary } from '@/api/endpoints/meta'
import { MetaABTestView } from './MetaABTestView'

const meta = {
  title: 'Pages/Meta/ABTestView',
  component: MetaABTestView,
} satisfies Meta<typeof MetaABTestView>

export default meta
type Story = StoryObj<typeof meta>

const controlMetrics = {
  group: 'control' as const,
  agentCount: 10,
  observationCount: 20,
  avgQualityScore: 7.5,
  avgSuccessRate: 0.85,
  totalSpendUsd: 100.0,
}

const treatmentMetrics = {
  group: 'treatment' as const,
  agentCount: 10,
  observationCount: 20,
  avgQualityScore: 8.2,
  avgSuccessRate: 0.91,
  totalSpendUsd: 95.0,
}

const baseTest: ABTestSummary = {
  proposalId: '550e8400-e29b-41d4-a716-446655440000',
  proposalTitle: 'Increase collaboration threshold',
  controlMetrics,
  treatmentMetrics,
  verdict: null,
  observationHoursElapsed: 24,
  observationHoursTotal: 48,
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
    tests: [{ ...baseTest, verdict: 'treatment_wins', observationHoursElapsed: 48 }],
  },
}

/** Inconclusive result. */
export const Inconclusive: Story = {
  args: {
    tests: [{ ...baseTest, verdict: 'inconclusive', observationHoursElapsed: 48 }],
  },
}

/** Treatment regressed. */
export const TreatmentRegressed: Story = {
  args: {
    tests: [
      {
        ...baseTest,
        verdict: 'treatment_regressed',
        observationHoursElapsed: 12,
        treatmentMetrics: {
          ...treatmentMetrics,
          avgQualityScore: 5.0,
          avgSuccessRate: 0.65,
        },
      },
    ],
  },
}
