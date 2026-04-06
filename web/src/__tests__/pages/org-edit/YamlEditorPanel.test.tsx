import { render, screen } from '@testing-library/react'
import { YamlEditorPanel } from '@/pages/org-edit/YamlEditorPanel'
import { makeCompanyConfig } from '../../helpers/factories'

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

  it('renders the textarea as editable', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText(/yaml editor/i)
    expect(textarea).not.toHaveAttribute('readonly')
  })

  it('renders Save and Reset buttons', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    expect(screen.getByText('Save YAML')).toBeInTheDocument()
    expect(screen.getByText('Reset')).toBeInTheDocument()
  })

  it('disables Save YAML button when form is not dirty', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const saveButton = screen.getByText('Save YAML').closest('button')!
    expect(saveButton).toBeDisabled()
  })
})
