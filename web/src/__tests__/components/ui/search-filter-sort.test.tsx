import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { SearchFilterSort } from '@/components/ui/search-filter-sort'
import { SearchInput } from '@/components/ui/search-input'

describe('SearchFilterSort', () => {
  it('renders slots', () => {
    render(
      <SearchFilterSort
        search={<span data-testid="s">search</span>}
        filters={<span data-testid="f">filters</span>}
        sort={<span data-testid="so">sort</span>}
        trailing={<span data-testid="t">trailing</span>}
      />,
    )
    expect(screen.getByTestId('s')).toBeInTheDocument()
    expect(screen.getByTestId('f')).toBeInTheDocument()
    expect(screen.getByTestId('so')).toBeInTheDocument()
    expect(screen.getByTestId('t')).toBeInTheDocument()
  })

  it('group has aria-label', () => {
    render(<SearchFilterSort search={<span>x</span>} />)
    expect(screen.getByRole('group', { name: 'List controls' })).toBeInTheDocument()
  })
})

describe('SearchInput', () => {
  it('renders with ariaLabel', () => {
    render(<SearchInput value="" onChange={() => {}} ariaLabel="Search agents" />)
    expect(screen.getByRole('searchbox', { name: 'Search agents' })).toBeInTheDocument()
  })

  it('fires onChange with each emitted character', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SearchInput value="" onChange={onChange} />)
    await user.type(screen.getByRole('searchbox'), 'hello')
    // userEvent.type fires controlled-input-style callbacks per keystroke.
    // Assert both the call count and the last emitted value.
    expect(onChange).toHaveBeenCalledTimes(5)
    expect(onChange).toHaveBeenLastCalledWith('o')
  })

  it('shows clear button when value is non-empty', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SearchInput value="abc" onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('does not show clear button when value is empty', () => {
    render(<SearchInput value="" onChange={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Clear search' })).not.toBeInTheDocument()
  })

  it('focusShortcut: pressing / focuses the input', () => {
    render(<SearchInput value="" onChange={() => {}} focusShortcut />)
    const input = screen.getByRole('searchbox')
    expect(input).not.toHaveFocus()
    act(() => {
      fireEvent.keyDown(window, { key: '/' })
    })
    expect(input).toHaveFocus()
  })

  it('focusShortcut: / with modifier keys is ignored', () => {
    render(<SearchInput value="" onChange={() => {}} focusShortcut />)
    const input = screen.getByRole('searchbox')
    expect(input).not.toHaveFocus()
    act(() => {
      fireEvent.keyDown(window, { key: '/', metaKey: true })
    })
    expect(input).not.toHaveFocus()
    act(() => {
      fireEvent.keyDown(window, { key: '/', ctrlKey: true })
    })
    expect(input).not.toHaveFocus()
  })

  it('focusShortcut off: pressing / does nothing', () => {
    render(<SearchInput value="" onChange={() => {}} />)
    const input = screen.getByRole('searchbox')
    expect(input).not.toHaveFocus()
    act(() => {
      fireEvent.keyDown(window, { key: '/' })
    })
    expect(input).not.toHaveFocus()
  })

  it('property: clear button is visible iff value.length > 0 (with disabled=false)', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0, maxLength: 30 }), (value) => {
        const { unmount } = render(<SearchInput value={value} onChange={() => {}} />)
        const clear = screen.queryByRole('button', { name: 'Clear search' })
        if (value.length > 0) {
          expect(clear).toBeInTheDocument()
        } else {
          expect(clear).not.toBeInTheDocument()
        }
        unmount()
      }),
    )
  })

  it('disabled: clear button hidden and / shortcut inactive', () => {
    render(<SearchInput value="abc" onChange={() => {}} disabled focusShortcut />)
    expect(screen.queryByRole('button', { name: 'Clear search' })).not.toBeInTheDocument()
    const input = screen.getByRole('searchbox')
    expect(input).not.toHaveFocus()
    act(() => {
      fireEvent.keyDown(window, { key: '/' })
    })
    expect(input).not.toHaveFocus()
  })
})
