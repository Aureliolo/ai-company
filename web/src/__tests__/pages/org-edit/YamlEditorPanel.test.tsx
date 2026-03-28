import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { YamlEditorPanel } from '@/pages/org-edit/YamlEditorPanel'
import { makeCompanyConfig } from '../../helpers/factories'

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

  it('disables Save button when not dirty', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    expect(screen.getByText('Save YAML').closest('button')).toBeDisabled()
  })

  it('enables Save button after editing', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: 'company_name: Changed\n' } })
    expect(screen.getByText('Save YAML').closest('button')).not.toBeDisabled()
  })

  it('shows unsaved changes indicator after editing', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: 'company_name: Changed\n' } })
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  })

  it('shows parse error for invalid YAML', async () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: '- just an array\n' } })
    fireEvent.click(screen.getByText('Save YAML'))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('shows validation error for missing company_name', async () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: 'agents: []\n' } })
    fireEvent.click(screen.getByText('Save YAML'))
    expect(await screen.findByText(/company_name/)).toBeInTheDocument()
  })

  it('calls onSave with parsed object on valid YAML', async () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={false} />)
    const textarea = screen.getByLabelText('YAML editor')
    fireEvent.change(textarea, { target: { value: 'company_name: Updated\nagents: []\ndepartments: []\n' } })
    fireEvent.click(screen.getByText('Save YAML'))
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith(expect.objectContaining({
        company_name: 'Updated',
      }))
    })
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

  it('disables buttons when saving', () => {
    render(<YamlEditorPanel config={makeCompanyConfig()} onSave={mockOnSave} saving={true} />)
    expect(screen.getByText('Saving...').closest('button')).toBeDisabled()
  })
})
