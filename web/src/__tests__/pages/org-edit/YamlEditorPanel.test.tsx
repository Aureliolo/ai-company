import { render, screen } from '@testing-library/react'
import { YamlEditorPanel } from '@/pages/org-edit/YamlEditorPanel'
import { makeCompanyConfig } from '../../helpers/factories'

// The YAML panel is read-only while the backend CRUD endpoints are
// pending (#1081).  When the endpoints land, restore the
// parse/validation/save/reset tests that were here previously --
// see git history on this file.

describe('YamlEditorPanel', () => {
  const mockOnSave = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => vi.resetAllMocks())

  it('renders textarea with YAML content', () => {
    const config = makeCompanyConfig()
    render(<YamlEditorPanel config={config} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText(/yaml editor/i)
    expect(textarea).toBeInTheDocument()
    expect((textarea as HTMLTextAreaElement).value).toContain('company_name')
  })

  it('renders the textarea as read-only while #1081 is gated', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText(/yaml editor/i)
    expect(textarea).toHaveAttribute('readonly')
    // ARIA label must not expose internal issue numbers to screen readers
    expect(textarea.getAttribute('aria-label')).not.toContain('#')
  })

  it('renders Save and Reset buttons', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    expect(screen.getByText('Save YAML')).toBeInTheDocument()
    expect(screen.getByText('Reset')).toBeInTheDocument()
  })

  it('disables Save YAML button with #1081 tooltip', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const saveButton = screen.getByText('Save YAML').closest('button')!
    expect(saveButton).toBeDisabled()
    expect(saveButton.getAttribute('title') ?? '').toContain('1081')
  })
})
