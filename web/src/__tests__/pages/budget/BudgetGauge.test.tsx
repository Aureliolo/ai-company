import { render, screen } from '@testing-library/react'
import { BudgetGauge } from '@/pages/budget/BudgetGauge'

describe('BudgetGauge', () => {
  it('renders section title', () => {
    render(
      <BudgetGauge usedPercent={20} budgetRemaining={400} daysUntilExhausted={null} />,
    )
    expect(screen.getByText('Budget Status')).toBeInTheDocument()
  })

  it('shows formatted remaining budget', () => {
    render(
      <BudgetGauge usedPercent={20} budgetRemaining={350.5} daysUntilExhausted={null} />,
    )
    // formatCurrency defaults to EUR
    expect(screen.getByText(/350\.50/)).toBeInTheDocument()
    expect(screen.getByText('remaining')).toBeInTheDocument()
  })

  it('shows "No exhaustion projected" when daysUntilExhausted is null', () => {
    render(
      <BudgetGauge usedPercent={20} budgetRemaining={400} daysUntilExhausted={null} />,
    )
    expect(screen.getByText('No exhaustion projected')).toBeInTheDocument()
  })

  it('shows projected exhaustion date when daysUntilExhausted is a number', () => {
    render(
      <BudgetGauge usedPercent={65} budgetRemaining={175} daysUntilExhausted={12} />,
    )
    expect(screen.getByText(/Projected exhaustion:/)).toBeInTheDocument()
    // Should not show the fallback text
    expect(screen.queryByText('No exhaustion projected')).not.toBeInTheDocument()
  })

  it('renders progress gauge with inverted value', () => {
    const { container } = render(
      <BudgetGauge usedPercent={85} budgetRemaining={75} daysUntilExhausted={3} />,
    )
    // ProgressGauge renders a meter element with aria-valuenow
    // 100 - 85 = 15
    const meter = container.querySelector('[role="meter"]')
    expect(meter).toBeInTheDocument()
    expect(meter).toHaveAttribute('aria-valuenow', '15')
  })

  it('clamps gauge value to 0 when usage exceeds 100%', () => {
    const { container } = render(
      <BudgetGauge usedPercent={110} budgetRemaining={0} daysUntilExhausted={0} />,
    )
    const meter = container.querySelector('[role="meter"]')
    expect(meter).toHaveAttribute('aria-valuenow', '0')
  })

  it('renders with custom currency', () => {
    render(
      <BudgetGauge
        usedPercent={50}
        budgetRemaining={250}
        daysUntilExhausted={null}
        currency="USD"
      />,
    )
    expect(screen.getByText(/\$250\.00/)).toBeInTheDocument()
  })
})
