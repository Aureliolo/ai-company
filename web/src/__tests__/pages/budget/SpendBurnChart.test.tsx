import { render, screen } from '@testing-library/react'
import { SpendBurnChart } from '@/pages/budget/SpendBurnChart'
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
  days_until_exhausted: 15,
  confidence: 0.85,
  avg_daily_spend: 6.2,
  currency: 'EUR',
}

const SAMPLE_ALERTS = {
  warn_at: 75,
  critical_at: 90,
  hard_stop_at: 100,
}

describe('SpendBurnChart', () => {
  it('renders section title', () => {
    render(
      <SpendBurnChart trendData={[]} forecast={null} budgetTotal={500} />,
    )
    expect(screen.getByText('Spend Burn')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(
      <SpendBurnChart trendData={[]} forecast={null} budgetTotal={500} />,
    )
    expect(screen.getByText('No spend data available')).toBeInTheDocument()
  })

  it('renders chart container when data is provided', () => {
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={SAMPLE_FORECAST}
        budgetTotal={500}
      />,
    )
    expect(screen.getByTestId('spend-burn-chart')).toBeInTheDocument()
  })

  it('renders without forecast', () => {
    render(
      <SpendBurnChart trendData={SAMPLE_TREND} forecast={null} budgetTotal={500} />,
    )
    expect(screen.getByTestId('spend-burn-chart')).toBeInTheDocument()
  })

  it('renders remaining stat pill when budgetRemaining is provided', () => {
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={null}
        budgetTotal={500}
        budgetRemaining={350}
      />,
    )
    expect(screen.getByText('Remaining')).toBeInTheDocument()
  })

  it('renders forecast stat pills when forecast is available', () => {
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={SAMPLE_FORECAST}
        budgetTotal={500}
      />,
    )
    expect(screen.getByText('Avg/day')).toBeInTheDocument()
    expect(screen.getByText('Days left')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('renders confidence stat pill when forecast is available', () => {
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={SAMPLE_FORECAST}
        budgetTotal={500}
      />,
    )
    expect(screen.getByText('Confidence')).toBeInTheDocument()
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('does not render days left when days_until_exhausted is null', () => {
    const forecastNoDays = { ...SAMPLE_FORECAST, days_until_exhausted: null }
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={forecastNoDays}
        budgetTotal={500}
      />,
    )
    expect(screen.queryByText('Days left')).not.toBeInTheDocument()
    // Confidence should still render
    expect(screen.getByText('Confidence')).toBeInTheDocument()
  })

  it('renders with alerts configuration', () => {
    render(
      <SpendBurnChart
        trendData={SAMPLE_TREND}
        forecast={SAMPLE_FORECAST}
        budgetTotal={500}
        alerts={SAMPLE_ALERTS}
      />,
    )
    expect(screen.getByTestId('spend-burn-chart')).toBeInTheDocument()
  })
})
