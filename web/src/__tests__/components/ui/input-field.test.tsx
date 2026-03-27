import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InputField } from '@/components/ui/input-field'

describe('InputField', () => {
  it('renders label text', () => {
    render(<InputField label="Company Name" />)
    expect(screen.getByLabelText('Company Name')).toBeInTheDocument()
  })

  it('renders required indicator when required', () => {
    render(<InputField label="Name" required />)
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('does not render required indicator when not required', () => {
    render(<InputField label="Name" />)
    expect(screen.queryByText('*')).not.toBeInTheDocument()
  })

  it('renders error message', () => {
    render(<InputField label="Name" error="Name is required" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Name is required')
  })

  it('sets aria-invalid when error is present', () => {
    render(<InputField label="Name" error="Required" />)
    expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true')
  })

  it('does not set aria-invalid when no error', () => {
    render(<InputField label="Name" />)
    expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid', 'false')
  })

  it('renders hint text when no error', () => {
    render(<InputField label="Name" hint="Max 200 characters" />)
    expect(screen.getByText('Max 200 characters')).toBeInTheDocument()
  })

  it('hides hint when error is present', () => {
    render(<InputField label="Name" hint="Max 200 chars" error="Required" />)
    expect(screen.queryByText('Max 200 chars')).not.toBeInTheDocument()
    expect(screen.getByText('Required')).toBeInTheDocument()
  })

  it('renders as textarea when multiline', () => {
    render(<InputField label="Description" multiline rows={4} />)
    const textarea = screen.getByLabelText('Description')
    expect(textarea.tagName).toBe('TEXTAREA')
  })

  it('handles user input', async () => {
    const user = userEvent.setup()
    render(<InputField label="Name" />)
    const input = screen.getByLabelText('Name')
    await user.type(input, 'Acme Corp')
    expect(input).toHaveValue('Acme Corp')
  })

  it('respects disabled state', () => {
    render(<InputField label="Name" disabled />)
    expect(screen.getByLabelText('Name')).toBeDisabled()
  })
})
