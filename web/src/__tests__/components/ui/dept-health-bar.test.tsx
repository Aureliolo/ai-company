import { render, screen } from '@testing-library/react'
import { DeptHealthBar } from '@/components/ui/dept-health-bar'

describe('DeptHealthBar', () => {
  it('renders department name', () => {
    render(<DeptHealthBar name="Engineering" health={85} agentCount={5} taskCount={12} />)

    expect(screen.getByText('Engineering')).toBeInTheDocument()
  })

  it('renders health percentage', () => {
    render(<DeptHealthBar name="Engineering" health={85} agentCount={5} taskCount={12} />)

    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('renders agent count', () => {
    render(<DeptHealthBar name="Engineering" health={85} agentCount={5} taskCount={12} />)

    expect(screen.getByText(/5 agents/)).toBeInTheDocument()
  })

  it('renders task count', () => {
    render(<DeptHealthBar name="Engineering" health={85} agentCount={5} taskCount={12} />)

    expect(screen.getByText(/12 tasks/)).toBeInTheDocument()
  })

  it('clamps health to 0-100 range', () => {
    render(<DeptHealthBar name="Engineering" health={120} agentCount={1} taskCount={1} />)

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('handles zero health', () => {
    render(<DeptHealthBar name="Broken" health={0} agentCount={0} taskCount={0} />)

    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('has accessible meter role', () => {
    render(<DeptHealthBar name="Eng" health={75} agentCount={3} taskCount={8} />)

    const meter = screen.getByRole('meter')
    expect(meter).toHaveAttribute('aria-valuenow', '75')
  })

  it('applies custom className', () => {
    const { container } = render(
      <DeptHealthBar name="Eng" health={75} agentCount={3} taskCount={8} className="my-class" />,
    )

    expect(container.firstChild).toHaveClass('my-class')
  })
})
