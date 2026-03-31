import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TagInput } from '@/components/ui/tag-input'

describe('TagInput', () => {
  it('renders each value as a removable tag', () => {
    render(<TagInput value={['alpha', 'beta']} onChange={() => {}} />)
    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
  })

  it('adds a tag on Enter', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={['a']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.type(input, 'b{Enter}')
    expect(onChange).toHaveBeenCalledWith(['a', 'b'])
  })

  it('removes last tag on Backspace when input is empty', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={['a', 'b']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.click(input)
    await user.keyboard('{Backspace}')
    expect(onChange).toHaveBeenCalledWith(['a'])
  })

  it('removes a specific tag when X is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={['a', 'b', 'c']} onChange={onChange} />)
    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    await user.click(removeButtons[1]!) // Remove 'b'
    expect(onChange).toHaveBeenCalledWith(['a', 'c'])
  })

  it('splits pasted text on commas', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={[]} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.click(input)
    await user.paste('x, y, z')
    // Paste handler should split and add items
    expect(onChange).toHaveBeenCalledWith(['x', 'y', 'z'])
  })

  it('does not add empty tags', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={['a']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.type(input, '   {Enter}')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('does not add duplicate tags', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<TagInput value={['a']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await user.type(input, 'a{Enter}')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('disables input when disabled prop is true', () => {
    render(<TagInput value={['a']} onChange={() => {}} disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('renders placeholder when no tags', () => {
    render(<TagInput value={[]} onChange={() => {}} placeholder="Add items..." />)
    expect(screen.getByPlaceholderText('Add items...')).toBeInTheDocument()
  })
})
