import { render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { PeriodSelector } from '@/pages/budget/PeriodSelector'
import type { AggregationPeriod } from '@/utils/budget'

describe('PeriodSelector', () => {
  const onChange = vi.fn()

  afterEach(() => {
    onChange.mockClear()
  })

  it('renders 3 radio buttons', () => {
    render(<PeriodSelector value="daily" onChange={onChange} />)
    const buttons = screen.getAllByRole('radio')
    expect(buttons).toHaveLength(3)
  })

  it('renders labels for all periods', () => {
    render(<PeriodSelector value="daily" onChange={onChange} />)
    expect(screen.getByText('Hourly')).toBeInTheDocument()
    expect(screen.getByText('Daily')).toBeInTheDocument()
    expect(screen.getByText('Weekly')).toBeInTheDocument()
  })

  it('marks the active period as checked', () => {
    render(<PeriodSelector value="daily" onChange={onChange} />)
    expect(screen.getByText('Daily')).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('Hourly')).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('Weekly')).toHaveAttribute('aria-checked', 'false')
  })

  it.each<AggregationPeriod>(['hourly', 'daily', 'weekly'])(
    'marks %s as checked when active',
    (period) => {
      render(<PeriodSelector value={period} onChange={onChange} />)
      const buttons = screen.getAllByRole('radio')
      const checked = buttons.filter(
        (btn) => btn.getAttribute('aria-checked') === 'true',
      )
      expect(checked).toHaveLength(1)
    },
  )

  it('fires onChange when clicking a different period', async () => {
    const user = userEvent.setup()
    render(<PeriodSelector value="daily" onChange={onChange} />)
    await user.click(screen.getByText('Weekly'))
    expect(onChange).toHaveBeenCalledWith('weekly')
  })

  it('fires onChange when clicking the current period', async () => {
    const user = userEvent.setup()
    render(<PeriodSelector value="daily" onChange={onChange} />)
    await user.click(screen.getByText('Daily'))
    expect(onChange).toHaveBeenCalledWith('daily')
  })

  it('has radiogroup role with aria-label', () => {
    render(<PeriodSelector value="daily" onChange={onChange} />)
    const group = screen.getByRole('radiogroup')
    expect(group).toHaveAttribute('aria-label', 'Aggregation period')
  })

  it('all buttons have type="button"', () => {
    render(<PeriodSelector value="daily" onChange={onChange} />)
    const buttons = screen.getAllByRole('radio')
    for (const btn of buttons) {
      expect(btn).toHaveAttribute('type', 'button')
    }
  })
})
