import type { Meta, StoryObj } from '@storybook/react'
import { BudgetBurnChart } from './BudgetBurnChart'
import { DEFAULT_CURRENCY } from '@/utils/currencies'

const TREND_DATA = [
  { timestamp: '2026-03-18', value: 4.2 },
  { timestamp: '2026-03-19', value: 5.8 },
  { timestamp: '2026-03-20', value: 6.1 },
  { timestamp: '2026-03-21', value: 5.5 },
  { timestamp: '2026-03-22', value: 7.3 },
  { timestamp: '2026-03-23', value: 6.9 },
  { timestamp: '2026-03-24', value: 8.1 },
]

const FORECAST = {
  horizon_days: 7,
  projected_total: 65,
  daily_projections: [
    { day: '2026-03-25', projected_spend: 8.5 },
    { day: '2026-03-26', projected_spend: 9.0 },
    { day: '2026-03-27', projected_spend: 9.2 },
    { day: '2026-03-28', projected_spend: 9.5 },
  ],
  days_until_exhausted: 45,
  confidence: 0.82,
  avg_daily_spend: 6.27,
  currency: DEFAULT_CURRENCY,
}

const meta = {
  title: 'Dashboard/BudgetBurnChart',
  component: BudgetBurnChart,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-2xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof BudgetBurnChart>

export default meta
type Story = StoryObj<typeof meta>

export const WithForecast: Story = {
  args: {
    trendData: TREND_DATA,
    forecast: FORECAST,
    budgetTotal: 500,
  },
}

export const WithoutForecast: Story = {
  args: {
    trendData: TREND_DATA,
    forecast: null,
    budgetTotal: 500,
  },
}

export const Empty: Story = {
  args: {
    trendData: [],
    forecast: null,
    budgetTotal: 500,
  },
}

const NEAR_BUDGET_TREND = TREND_DATA.map((p) => ({ ...p, value: p.value * 10 }))
const NEAR_BUDGET_FORECAST = {
  ...FORECAST,
  projected_total: FORECAST.projected_total * 10,
  avg_daily_spend: FORECAST.avg_daily_spend * 10,
  days_until_exhausted: 4,
  daily_projections: FORECAST.daily_projections.map((p) => ({
    ...p,
    projected_spend: p.projected_spend * 10,
  })),
}

export const NearBudget: Story = {
  args: {
    trendData: NEAR_BUDGET_TREND,
    forecast: NEAR_BUDGET_FORECAST,
    budgetTotal: 100,
  },
}
