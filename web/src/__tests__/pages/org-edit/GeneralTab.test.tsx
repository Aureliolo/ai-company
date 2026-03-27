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

  it('calls onUpdate when save is clicked', async () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={false} />)
    fireEvent.click(screen.getByText('Save Settings'))
    expect(mockOnUpdate).toHaveBeenCalledTimes(1)
  })

  it('disables save button when saving', () => {
    const config = makeCompanyConfig()
    render(<GeneralTab config={config} onUpdate={mockOnUpdate} saving={true} />)
    expect(screen.getByText('Save Settings').closest('button')).toBeDisabled()
  })
})
