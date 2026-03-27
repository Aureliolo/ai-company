import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import { SliderField } from '@/components/ui/slider-field'

describe('SliderField', () => {
  it('renders label text', () => {
    render(<SliderField label="Team Size" value={5} min={1} max={20} onChange={() => {}} />)
    expect(screen.getByLabelText('Team Size')).toBeInTheDocument()
  })

  it('displays current value', () => {
    render(<SliderField label="Team Size" value={5} min={1} max={20} onChange={() => {}} />)
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('displays formatted value when formatValue is provided', () => {
    render(
      <SliderField
        label="Budget"
        value={100}
        min={10}
        max={500}
        formatValue={(v) => `$${v}`}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('$100')).toBeInTheDocument()
  })

  it('displays formatted min and max labels', () => {
    render(
      <SliderField
        label="Budget"
        value={100}
        min={10}
        max={500}
        formatValue={(v) => `$${v}`}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('$10')).toBeInTheDocument()
    expect(screen.getByText('$500')).toBeInTheDocument()
  })

  it('sets correct ARIA attributes', () => {
    render(<SliderField label="Team Size" value={5} min={1} max={20} onChange={() => {}} />)
    const slider = screen.getByRole('slider')
    expect(slider).toHaveAttribute('aria-valuemin', '1')
    expect(slider).toHaveAttribute('aria-valuemax', '20')
    expect(slider).toHaveAttribute('aria-valuenow', '5')
  })

  it('respects disabled state', () => {
    render(<SliderField label="Team Size" value={5} min={1} max={20} disabled onChange={() => {}} />)
    expect(screen.getByRole('slider')).toBeDisabled()
  })

  it('has aria-live on value display', () => {
    render(<SliderField label="Team Size" value={5} min={1} max={20} onChange={() => {}} />)
    expect(screen.getByText('5')).toHaveAttribute('aria-live', 'polite')
  })

  it('calls onChange with new value on input', () => {
    const handleChange = vi.fn()
    render(<SliderField label="Team Size" value={5} min={1} max={20} onChange={handleChange} />)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '10' } })
    expect(handleChange).toHaveBeenCalledWith(10)
  })
})
