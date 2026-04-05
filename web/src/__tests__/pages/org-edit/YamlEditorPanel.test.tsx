import { render, screen, fireEvent } from '@testing-library/react'
import { YamlEditorPanel } from '@/pages/org-edit/YamlEditorPanel'
import { makeCompanyConfig } from '../../helpers/factories'

// Save is disabled while the backend CRUD endpoints are pending
// (#1081).  When the endpoints land, remove the "disables Save" test
// and restore the parse/validation/save click-behaviour tests that
// were here previously -- see git history on this file.

describe('YamlEditorPanel', () => {
  const mockOnSave = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => vi.resetAllMocks())

  it('renders textarea with YAML content', () => {
    const config = makeCompanyConfig()
    render(<YamlEditorPanel config={config} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    expect(textarea).toBeInTheDocument()
    expect((textarea as HTMLTextAreaElement).value).toContain('company_name')
  })

  it('renders Save and Reset buttons', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    expect(screen.getByText('Save YAML')).toBeInTheDocument()
    expect(screen.getByText('Reset')).toBeInTheDocument()
  })

  it('shows unsaved changes indicator after editing', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: 'company_name: Changed\n' } })
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  })

  it('disables Save YAML button with #1081 tooltip even when dirty', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    // Make the panel dirty.  The Save button must stay disabled.
    fireEvent.change(textarea, { target: { value: 'company_name: Updated\nagents: []\ndepartments: []\n' } })
    const saveButton = screen.getByText('Save YAML').closest('button')!
    expect(saveButton).toBeDisabled()
    expect(saveButton.getAttribute('title') ?? '').toContain('1081')
    // Clicking the disabled button must not call onSave.
    fireEvent.click(saveButton)
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('resets textarea to original config on Reset click', () => {
    const config = makeCompanyConfig()
    render(<YamlEditorPanel config={config} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor') as HTMLTextAreaElement
    const original = textarea.value
    fireEvent.change(textarea, { target: { value: 'company_name: Changed\n' } })
    expect(textarea.value).toBe('company_name: Changed\n')
    fireEvent.click(screen.getByText('Reset'))
    expect(textarea.value).toBe(original)
  })
})
