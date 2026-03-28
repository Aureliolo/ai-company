import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { vi, describe, it, expect } from 'vitest'
import { SegmentedControl } from '@/components/ui/segmented-control'

const options = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Beta' },
  { value: 'c', label: 'Gamma' },
] as const

describe('SegmentedControl', () => {
  it('renders all options', () => {
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={() => {}} />,
    )
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('marks the selected option as checked', () => {
    render(
      <SegmentedControl label="Test" options={[...options]} value="b" onChange={() => {}} />,
    )
    const beta = screen.getByRole('radio', { name: 'Beta' })
    expect(beta).toHaveAttribute('aria-checked', 'true')

    const alpha = screen.getByRole('radio', { name: 'Alpha' })
    expect(alpha).toHaveAttribute('aria-checked', 'false')
  })

  it('calls onChange when clicking an option', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={onChange} />,
    )

    await user.click(screen.getByText('Gamma'))
    expect(onChange).toHaveBeenCalledWith('c')
  })

  it('does not call onChange when clicking disabled option', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const optionsWithDisabled = [
      { value: 'a', label: 'Alpha' },
      { value: 'b', label: 'Beta', disabled: true },
    ]
    render(
      <SegmentedControl label="Test" options={optionsWithDisabled} value="a" onChange={onChange} />,
    )

    await user.click(screen.getByText('Beta'))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('renders as disabled when disabled prop is true', () => {
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={() => {}} disabled />,
    )
    const buttons = screen.getAllByRole('radio')
    for (const btn of buttons) {
      expect(btn).toBeDisabled()
    }
  })

  it('has an accessible radiogroup with label', () => {
    render(
      <SegmentedControl label="Density" options={[...options]} value="a" onChange={() => {}} />,
    )
    const group = screen.getByRole('radiogroup', { name: 'Density' })
    expect(group).toBeInTheDocument()
  })

  it('navigates with ArrowRight key', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={onChange} />,
    )

    const alpha = screen.getByRole('radio', { name: 'Alpha' })
    alpha.focus()
    await user.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('navigates with ArrowLeft key and wraps around', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={onChange} />,
    )

    const alpha = screen.getByRole('radio', { name: 'Alpha' })
    alpha.focus()
    await user.keyboard('{ArrowLeft}')
    expect(onChange).toHaveBeenCalledWith('c')
  })

  it('navigates with ArrowDown key to next option', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={onChange} />,
    )

    const alpha = screen.getByRole('radio', { name: 'Alpha' })
    alpha.focus()
    await user.keyboard('{ArrowDown}')
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('navigates with ArrowUp key and wraps from first to last', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <SegmentedControl label="Test" options={[...options]} value="a" onChange={onChange} />,
    )

    const alpha = screen.getByRole('radio', { name: 'Alpha' })
    alpha.focus()
    await user.keyboard('{ArrowUp}')
    expect(onChange).toHaveBeenCalledWith('c')
  })

  it('keyboard navigation skips disabled options', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const optionsWithMiddleDisabled = [
      { value: 'x', label: 'Xray' },
      { value: 'y', label: 'Yankee', disabled: true },
      { value: 'z', label: 'Zulu' },
    ]
    render(
      <SegmentedControl
        label="Test"
        options={optionsWithMiddleDisabled}
        value="x"
        onChange={onChange}
      />,
    )

    const xray = screen.getByRole('radio', { name: 'Xray' })
    xray.focus()
    await user.keyboard('{ArrowRight}')
    // Should skip 'y' (disabled) and land on 'z'
    expect(onChange).toHaveBeenCalledWith('z')
  })

  describe('fast-check property tests', () => {
    it('ArrowRight wraps correctly for any enabled option count', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 2, max: 10 }),
          fc.nat(),
          (count, startSeed) => {
            const dynamicOptions = Array.from({ length: count }, (_, i) => ({
              value: `opt-${i}`,
              label: `Option ${i}`,
            }))
            const startIndex = startSeed % count
            const startValue = `opt-${startIndex}`
            const expectedNextIndex = (startIndex + 1) % count
            const expectedValue = `opt-${expectedNextIndex}`

            const onChange = vi.fn()
            const { unmount } = render(
              <SegmentedControl
                label="Test"
                options={dynamicOptions}
                value={startValue}
                onChange={onChange}
              />,
            )

            const selected = screen.getByRole('radio', { name: `Option ${startIndex}` })
            selected.focus()
            // Simulate ArrowRight via direct keyDown event (synchronous)
            const event = new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })
            selected.dispatchEvent(event)

            expect(onChange).toHaveBeenCalledWith(expectedValue)
            unmount()
          },
        ),
      )
    })
  })
})
