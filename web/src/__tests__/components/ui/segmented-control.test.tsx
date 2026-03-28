import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
})
