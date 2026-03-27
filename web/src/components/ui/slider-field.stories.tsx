import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SliderField } from './slider-field'

const meta = {
  title: 'UI/SliderField',
  component: SliderField,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof SliderField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: 'Team Size', value: 5, min: 1, max: 20, onChange: () => {} },
}

export const WithFormat: Story = {
  args: {
    label: 'Budget Cap',
    value: 100,
    min: 10,
    max: 500,
    step: 10,
    formatValue: (v) => `$${v}`,
    onChange: () => {},
  },
}

export const Disabled: Story = {
  args: { label: 'Team Size', value: 5, min: 1, max: 20, disabled: true, onChange: () => {} },
}

function InteractiveSlider() {
  const [value, setValue] = useState(5)
  return (
    <SliderField
      label="Team Size"
      value={value}
      onChange={setValue}
      min={3}
      max={15}
      formatValue={(v) => `${v} agents`}
    />
  )
}

export const Interactive: Story = {
  args: { label: 'Team Size', value: 5, min: 3, max: 15, onChange: () => {} },
  render: () => <InteractiveSlider />,
}
