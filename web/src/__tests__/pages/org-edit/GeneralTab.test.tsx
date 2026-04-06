import { render, screen, fireEvent } from '@testing-library/react'
import { GeneralTab } from '@/pages/org-edit/GeneralTab'
import { makeCompanyConfig } from '../../helpers/factories'

describe('GeneralTab', () => {
  const mockOnUpdate = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when config is null', () => {
    render(<GeneralTab config={null} onUpdate={mockOnUpdate} saving={false} />)
    expect(screen.getByText('No company data')).toBeInTheDocument()
  })

  it('renders company name field with value from config', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    const input = screen.getByLabelText(/company name/i)
    expect(input).toHaveValue('Test Corp')
  })

  it('renders autonomy level select', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    expect(screen.getByLabelText(/autonomy level/i)).toBeInTheDocument()
  })

  it('renders monthly budget slider', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    expect(screen.getByLabelText(/monthly budget/i)).toBeInTheDocument()
  })

  it('renders communication pattern field', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    expect(screen.getByLabelText(/communication pattern/i)).toBeInTheDocument()
  })

  it('renders save button', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    expect(screen.getByText('Save Settings')).toBeInTheDocument()
  })

  it('disables Save Settings button until the form is dirty', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    const saveButton = screen.getByRole('button', { name: /save settings/i })
    expect(saveButton).toBeDisabled()
  })

  it('enables Save Settings button when the form is dirty', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: 'Updated Corp' },
    })
    const saveButton = screen.getByRole('button', { name: /save settings/i })
    expect(saveButton).not.toBeDisabled()
  })
})
