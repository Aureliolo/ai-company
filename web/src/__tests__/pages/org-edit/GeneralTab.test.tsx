import { render, screen, fireEvent } from '@testing-library/react'
import { GeneralTab } from '@/pages/org-edit/GeneralTab'
import { makeCompanyConfig } from '../../helpers/factories'

// Save is disabled while the backend CRUD endpoints are pending
// (#1081).  When the endpoints land, remove the "disables Save" test
// and restore the click-behaviour + property-based disablement tests
// that were here previously -- see git history on this file.

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

  it('disables Save Settings button with #1081 tooltip even when form is dirty', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    // Make the form dirty.  Before the backend gate, this would have
    // enabled the Save button; with the gate in place it must stay
    // disabled regardless of form state.
    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: 'Updated Corp' },
    })
    const saveButton = screen.getByRole('button', { name: /save settings/i })
    expect(saveButton).toBeDisabled()
    expect(saveButton.getAttribute('title') ?? '').toContain('1081')
    // Clicking the disabled button must not call onUpdate.
    fireEvent.click(saveButton)
    expect(mockOnUpdate).not.toHaveBeenCalled()
  })
})
