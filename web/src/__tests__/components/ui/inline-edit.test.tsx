import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as fc from 'fast-check'
import { InlineEdit } from '@/components/ui/inline-edit'

describe('InlineEdit', () => {
  it('renders display value initially', () => {
    render(<InlineEdit value="Hello" onSave={vi.fn()} />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('click switches to editing mode', async () => {
    const user = userEvent.setup()
    render(<InlineEdit value="Hello" onSave={vi.fn()} />)

    await user.click(screen.getByText('Hello'))
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('Hello')
  })

  it('Enter saves value', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<InlineEdit value="Hello" onSave={onSave} />)

    await user.click(screen.getByText('Hello'))
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'World')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('World')
    })
  })

  it('Escape cancels without saving', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<InlineEdit value="Hello" onSave={onSave} />)

    await user.click(screen.getByText('Hello'))
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'Changed')
    await user.keyboard('{Escape}')

    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('shows validation error', async () => {
    const user = userEvent.setup()
    render(
      <InlineEdit
        value="Hello"
        onSave={vi.fn()}
        validate={(v) => (v.length === 0 ? 'Required' : null)}
      />,
    )

    await user.click(screen.getByText('Hello'))
    await user.clear(screen.getByRole('textbox'))
    await user.keyboard('{Enter}')

    expect(screen.getByText('Required')).toBeInTheDocument()
  })

  it('can retry save after validation error', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <InlineEdit
        value="Hello"
        onSave={onSave}
        validate={(v) => (v.length === 0 ? 'Required' : null)}
      />,
    )

    // First attempt: clear and Enter triggers validation error
    await user.click(screen.getByText('Hello'))
    await user.clear(screen.getByRole('textbox'))
    await user.keyboard('{Enter}')
    expect(screen.getByText('Required')).toBeInTheDocument()

    // Second attempt: type valid value and save succeeds
    await user.type(screen.getByRole('textbox'), 'Valid')
    await user.keyboard('{Enter}')
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('Valid')
    })
  })

  it('error from save shows inline error', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockRejectedValue(new Error('Server error'))
    render(<InlineEdit value="Hello" onSave={onSave} />)

    await user.click(screen.getByText('Hello'))
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'Changed')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument()
    })
  })

  it('disabled prop prevents editing', async () => {
    const user = userEvent.setup()
    render(<InlineEdit value="Hello" onSave={vi.fn()} disabled />)

    await user.click(screen.getByText('Hello'))
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('custom renderDisplay is used', () => {
    render(
      <InlineEdit
        value="code"
        onSave={vi.fn()}
        renderDisplay={(v) => <code data-testid="custom">{v}</code>}
      />,
    )
    expect(screen.getByTestId('custom')).toHaveTextContent('code')
  })

  it('applies className', () => {
    const { container } = render(
      <InlineEdit value="Hello" onSave={vi.fn()} className="custom" />,
    )
    expect(container.firstChild).toHaveClass('custom')
  })

  it('saves on blur', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<InlineEdit value="original" onSave={onSave} />)

    // Enter edit mode
    await user.click(screen.getByText('original'))
    const input = screen.getByRole('textbox')

    // Change value and blur
    await user.clear(input)
    await user.type(input, 'updated')
    await user.tab()

    expect(onSave).toHaveBeenCalledWith('updated')
  })

  it('does not double-save on Enter followed by blur', async () => {
    const user = userEvent.setup()
    let resolveSave!: () => void
    const savePromise = new Promise<void>((resolve) => {
      resolveSave = resolve
    })
    const onSave = vi.fn().mockReturnValue(savePromise)
    render(<InlineEdit value="original" onSave={onSave} />)

    await user.click(screen.getByText('original'))
    const input = screen.getByRole('textbox')

    await user.clear(input)
    await user.type(input, 'changed')
    await user.keyboard('{Enter}')

    // Save is in-progress (promise unresolved) -- blur should be blocked by saveInProgressRef
    await user.tab()

    // Resolve the pending save
    resolveSave()
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    })

    // onSave should only be called once
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  describe('property: string values round-trip', () => {
    it('display renders generated values', () => {
      fc.assert(
        fc.property(fc.string({ minLength: 1, maxLength: 50 }), (value) => {
          const { container, unmount } = render(
            <InlineEdit value={value} onSave={vi.fn()} />,
          )
          // Value should be displayed
          const el = container.querySelector('[data-inline-display]')
          expect(el?.textContent).toBe(value)
          unmount()
        }),
      )
    })
  })
})
