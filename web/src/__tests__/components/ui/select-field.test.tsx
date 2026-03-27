import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SelectField } from '@/components/ui/select-field'

const options = [
  { value: 'EUR', label: 'EUR - Euro' },
  { value: 'USD', label: 'USD - US Dollar' },
  { value: 'GBP', label: 'GBP - British Pound' },
]

describe('SelectField', () => {
  it('renders label text', () => {
    render(<SelectField label="Currency" options={options} value="EUR" onChange={() => {}} />)
    expect(screen.getByLabelText('Currency')).toBeInTheDocument()
  })

  it('renders all options', () => {
    render(<SelectField label="Currency" options={options} value="EUR" onChange={() => {}} />)
    expect(screen.getAllByRole('option')).toHaveLength(3)
  })

  it('renders placeholder option when provided', () => {
    render(
      <SelectField
        label="Currency"
        options={options}
        value=""
        onChange={() => {}}
        placeholder="Select..."
      />,
    )
    expect(screen.getAllByRole('option')).toHaveLength(4)
    expect(screen.getByText('Select...')).toBeInTheDocument()
  })

  it('calls onChange with selected value', async () => {
    const handleChange = vi.fn()
    const user = userEvent.setup()
    render(<SelectField label="Currency" options={options} value="EUR" onChange={handleChange} />)
    await user.selectOptions(screen.getByLabelText('Currency'), 'USD')
    expect(handleChange).toHaveBeenCalledWith('USD')
  })

  it('renders error message', () => {
    render(
      <SelectField label="Currency" options={options} value="" onChange={() => {}} error="Required" />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Required')
  })

  it('sets aria-invalid when error is present', () => {
    render(
      <SelectField label="Currency" options={options} value="" onChange={() => {}} error="Required" />,
    )
    expect(screen.getByLabelText('Currency')).toHaveAttribute('aria-invalid', 'true')
  })

  it('renders required indicator', () => {
    render(
      <SelectField label="Currency" options={options} value="EUR" onChange={() => {}} required />,
    )
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('respects disabled state', () => {
    render(
      <SelectField label="Currency" options={options} value="EUR" onChange={() => {}} disabled />,
    )
    expect(screen.getByLabelText('Currency')).toBeDisabled()
  })
})
