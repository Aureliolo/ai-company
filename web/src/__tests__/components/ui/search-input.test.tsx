import { useRef } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SearchInput, type SearchInputHandle } from '@/components/ui/search-input'

describe('SearchInput', () => {
  it('calls onChange when the user types', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SearchInput value="" onChange={onChange} />)
    await user.type(screen.getByRole('searchbox'), 'ab')
    expect(onChange).toHaveBeenCalled()
  })

  it('renders a clear button only when value is non-empty', () => {
    const { rerender } = render(<SearchInput value="" onChange={() => {}} />)
    expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument()
    rerender(<SearchInput value="hello" onChange={() => {}} />)
    expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument()
  })

  it('clicking the clear button fires onChange with empty string', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SearchInput value="hello" onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /clear search/i }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('disables the input when disabled=true and hides the clear button', () => {
    render(<SearchInput value="locked" onChange={() => {}} disabled />)
    expect(screen.getByRole('searchbox')).toBeDisabled()
    expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument()
  })

  it('focuses the input when the "/" global shortcut fires and focusShortcut is enabled', async () => {
    const user = userEvent.setup()
    render(<SearchInput value="" onChange={() => {}} focusShortcut />)
    await user.keyboard('/')
    expect(screen.getByRole('searchbox')).toHaveFocus()
  })

  it('does not steal focus when the "/" shortcut fires and focusShortcut is off (default)', async () => {
    const user = userEvent.setup()
    render(
      <>
        <button type="button">Elsewhere</button>
        <SearchInput value="" onChange={() => {}} />
      </>,
    )
    const outside = screen.getByRole('button', { name: /elsewhere/i })
    outside.focus()
    await user.keyboard('/')
    expect(outside).toHaveFocus()
  })

  describe('maxWidth prop', () => {
    it('defaults to the "wide" token maxWidth', () => {
      render(<SearchInput value="" onChange={() => {}} />)
      const wrapper = screen.getByRole('searchbox').parentElement as HTMLElement
      expect(wrapper).toHaveStyle({ maxWidth: 'var(--so-search-max-wide)' })
    })

    it('applies the narrow token when maxWidth="narrow"', () => {
      render(<SearchInput value="" onChange={() => {}} maxWidth="narrow" />)
      const wrapper = screen.getByRole('searchbox').parentElement as HTMLElement
      expect(wrapper).toHaveStyle({ maxWidth: 'var(--so-search-max-narrow)' })
    })
  })

  describe('imperative ref', () => {
    it('exposes focus() and clear() handles', async () => {
      const user = userEvent.setup()
      imperativeHarnessOnChange.mockClear()

      render(<ImperativeHarness />)
      await user.click(screen.getByRole('button', { name: 'Focus' }))
      expect(screen.getByRole('searchbox')).toHaveFocus()
      await user.click(screen.getByRole('button', { name: 'Clear' }))
      expect(imperativeHarnessOnChange).toHaveBeenCalledWith('')
    })
  })
})

// Module-level harness for the imperative-ref test (keeps the component out
// of a function body so the @eslint-react/component-hook-factories rule is
// satisfied).
const imperativeHarnessOnChange = vi.fn()
function ImperativeHarness() {
  const ref = useRef<SearchInputHandle | null>(null)
  return (
    <>
      <button type="button" onClick={() => ref.current?.focus()}>Focus</button>
      <button type="button" onClick={() => ref.current?.clear()}>Clear</button>
      <SearchInput ref={ref} value="hello" onChange={imperativeHarnessOnChange} />
    </>
  )
}
