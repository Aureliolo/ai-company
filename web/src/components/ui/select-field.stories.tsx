import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SelectField } from './select-field'
import { CURRENCY_OPTIONS } from '@/utils/currencies'

const currencies = CURRENCY_OPTIONS.slice(0, 4)

const meta = {
  title: 'UI/SelectField',
  component: SelectField,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof SelectField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: 'Currency', options: currencies, value: 'EUR', onChange: () => {} },
}

export const WithPlaceholder: Story = {
  args: {
    label: 'Provider',
    options: [
      { value: 'openai', label: 'OpenAI-compatible' },
      { value: 'ollama', label: 'Ollama (local)' },
    ],
    value: '',
    onChange: () => {},
    placeholder: 'Select a provider...',
  },
}

export const WithError: Story = {
  args: {
    label: 'Currency',
    options: currencies,
    value: '',
    onChange: () => {},
    error: 'Please select a currency',
    required: true,
  },
}

export const Disabled: Story = {
  args: { label: 'Currency', options: currencies, value: 'EUR', onChange: () => {}, disabled: true },
}

function InteractiveSelect() {
  const [value, setValue] = useState('EUR')
  return <SelectField label="Currency" options={currencies} value={value} onChange={setValue} />
}

export const Interactive: Story = {
  args: { label: 'Currency', options: currencies, value: 'EUR', onChange: () => {} },
  render: () => <InteractiveSelect />,
}
