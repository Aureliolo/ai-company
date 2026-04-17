import { render, screen } from '@testing-library/react'
import { BudgetBurnChart } from '@/pages/dashboard/BudgetBurnChart'
import type { ForecastResponse, TrendDataPoint } from '@/api/types'

const SAMPLE_TREND: TrendDataPoint[] = [
  { timestamp: '2026-03-20', value: 5 },
  { timestamp: '2026-03-21', value: 6 },
  { timestamp: '2026-03-22', value: 7 },
  { timestamp: '2026-03-23', value: 5 },
  { timestamp: '2026-03-24', value: 8 },
]

const SAMPLE_FORECAST: ForecastResponse = {
  horizon_days: 7,
  projected_total: 60,
  daily_projections: [
    { day: '2026-03-27', projected_spend: 7 },
    { day: '2026-03-28', projected_spend: 7.5 },
  ],
  days_until_exhausted: null,
  confidence: 0.85,
  avg_daily_spend: 6.2,
  currency: 'EUR',
}

describe('BudgetBurnChart', () => {
  it('renders section title', () => {
    render(<BudgetBurnChart trendData={[]} forecast={null} budgetTotal={500} />)
    expect(screen.getByText('Budget Burn')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(<BudgetBurnChart trendData={[]} forecast={null} budgetTotal={500} />)
    expect(screen.getByText('No spend data available')).toBeInTheDocument()
  })

  it('renders chart when data is provided', () => {
    render(
      <BudgetBurnChart trendData={SAMPLE_TREND} forecast={SAMPLE_FORECAST} budgetTotal={500} />,
    )
    expect(screen.getByTestId('budget-burn-chart')).toBeInTheDocument()
  })

  it('renders without forecast', () => {
    render(
      <BudgetBurnChart trendData={SAMPLE_TREND} forecast={null} budgetTotal={500} />,
    )
    expect(screen.getByTestId('budget-burn-chart')).toBeInTheDocument()
  })

  it('renders forecast info when available', () => {
    render(
      <BudgetBurnChart trendData={SAMPLE_TREND} forecast={SAMPLE_FORECAST} budgetTotal={500} />,
    )
    expect(screen.getByText('Avg/day')).toBeInTheDocument()
    expect(screen.getByText(/6\.20/)).toBeInTheDocument()
  })

  it('renders days left when days_until_exhausted is non-null', () => {
    const forecastWithDays = { ...SAMPLE_FORECAST, days_until_exhausted: 12 }
    render(
      <BudgetBurnChart trendData={SAMPLE_TREND} forecast={forecastWithDays} budgetTotal={500} />,
    )
    expect(screen.getByText('Days left')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('renders remaining budget when provided', () => {
    render(
      <BudgetBurnChart trendData={SAMPLE_TREND} forecast={null} budgetTotal={500} budgetRemaining={350} />,
    )
    expect(screen.getByText('Remaining')).toBeInTheDocument()
  })
})
