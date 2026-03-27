import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToggleField } from '@/components/ui/toggle-field'

describe('ToggleField', () => {
  it('renders label text', () => {
    render(<ToggleField label="Enable" checked={false} onChange={() => {}} />)
    expect(screen.getByText('Enable')).toBeInTheDocument()
  })

  it('renders switch role', () => {
    render(<ToggleField label="Enable" checked={false} onChange={() => {}} />)
    expect(screen.getByRole('switch')).toBeInTheDocument()
  })

  it('reflects checked state via aria-checked', () => {
    const { rerender } = render(<ToggleField label="Enable" checked={false} onChange={() => {}} />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')

    rerender(<ToggleField label="Enable" checked={true} onChange={() => {}} />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
  })

  it('calls onChange with toggled value on click', async () => {
    const handleChange = vi.fn()
    const user = userEvent.setup()
    render(<ToggleField label="Enable" checked={false} onChange={handleChange} />)
    await user.click(screen.getByRole('switch'))
    expect(handleChange).toHaveBeenCalledWith(true)
  })

  it('calls onChange with false when unchecking', async () => {
    const handleChange = vi.fn()
    const user = userEvent.setup()
    render(<ToggleField label="Enable" checked={true} onChange={handleChange} />)
    await user.click(screen.getByRole('switch'))
    expect(handleChange).toHaveBeenCalledWith(false)
  })

  it('renders description text', () => {
    render(
      <ToggleField
        label="Budget limit"
        description="Prevents exceeding the limit"
        checked={false}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('Prevents exceeding the limit')).toBeInTheDocument()
  })

  it('respects disabled state', () => {
    render(<ToggleField label="Enable" checked={false} disabled onChange={() => {}} />)
    expect(screen.getByRole('switch')).toBeDisabled()
  })

  it('does not call onChange when disabled', async () => {
    const handleChange = vi.fn()
    const user = userEvent.setup()
    render(<ToggleField label="Enable" checked={false} disabled onChange={handleChange} />)
    await user.click(screen.getByRole('switch'))
    expect(handleChange).not.toHaveBeenCalled()
  })
})
