import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SegmentedControl } from './segmented-control'

const meta = {
  title: 'UI/SegmentedControl',
  component: SegmentedControl,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof SegmentedControl>

export default meta
type Story = StoryObj<typeof meta>

const densityOptions = [
  { value: 'dense', label: 'Dense' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'medium', label: 'Medium' },
  { value: 'sparse', label: 'Sparse' },
] as const

export const Default: Story = {
  args: {
    label: 'Density',
    options: [...densityOptions],
    value: 'balanced',
    onChange: () => {},
  },
}

export const SmallSize: Story = {
  args: {
    label: 'Density',
    options: [...densityOptions],
    value: 'dense',
    onChange: () => {},
    size: 'sm',
  },
}

export const MediumSize: Story = {
  args: {
    label: 'Density',
    options: [...densityOptions],
    value: 'balanced',
    onChange: () => {},
    size: 'md',
  },
}

export const Disabled: Story = {
  args: {
    label: 'Density',
    options: [...densityOptions],
    value: 'balanced',
    onChange: () => {},
    disabled: true,
  },
}

export const WithDisabledOption: Story = {
  args: {
    label: 'Animation',
    options: [
      { value: 'minimal', label: 'Minimal' },
      { value: 'spring', label: 'Spring', disabled: true },
      { value: 'instant', label: 'Instant' },
      { value: 'status-driven', label: 'Status' },
    ],
    value: 'minimal',
    onChange: () => {},
  },
}

// Note: SegmentedControl has no hover, loading, error, or empty states.
// Hover is CSS-only (handled by Tailwind hover: classes). Loading and error
// are not part of this component's API -- it is a stateless input control.
// Empty options would produce an invalid radiogroup; consumers are expected
// to always pass at least one option.

export const Interactive: Story = {
  args: {
    label: 'Mode',
    options: [...densityOptions],
    value: 'balanced',
    onChange: () => {},
  },
  render: function InteractiveControl() {
    const [value, setValue] = useState('balanced')
    return (
      <SegmentedControl
        label="Density"
        options={[...densityOptions]}
        value={value}
        onChange={setValue}
      />
    )
  },
}
