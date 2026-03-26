import { render, screen } from '@testing-library/react'
import { StatPill } from '@/components/ui/stat-pill'

describe('StatPill', () => {
  it('renders label text', () => {
    render(<StatPill label="Tasks" value={42} />)

    expect(screen.getByText('Tasks')).toBeInTheDocument()
  })

  it('renders numeric value', () => {
    render(<StatPill label="Tasks" value={42} />)

    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatPill label="Status" value="OK" />)

    expect(screen.getByText('OK')).toBeInTheDocument()
  })

  it('applies mono font class to value', () => {
    render(<StatPill label="Tasks" value={42} />)
    const value = screen.getByText('42')

    expect(value).toHaveClass('font-mono')
  })

  it('applies custom className', () => {
    const { container } = render(<StatPill label="X" value="Y" className="my-class" />)

    expect(container.firstChild).toHaveClass('my-class')
  })
})
