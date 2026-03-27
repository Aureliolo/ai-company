import type { Meta, StoryObj } from '@storybook/react'
import { InputField } from './input-field'

const meta = {
  title: 'UI/InputField',
  component: InputField,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof InputField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: 'Company Name', placeholder: 'Enter company name' },
}

export const Required: Story = {
  args: { label: 'Company Name', required: true, placeholder: 'Required field' },
}

export const WithError: Story = {
  args: { label: 'Company Name', error: 'Company name is required', required: true },
}

export const WithHint: Story = {
  args: { label: 'Description', hint: 'Max 1000 characters', placeholder: 'Optional description' },
}

export const Disabled: Story = {
  args: { label: 'Company Name', disabled: true, value: 'Acme Corp' },
}

export const Multiline: Story = {
  args: { label: 'Description', multiline: true, rows: 4, placeholder: 'Describe your company...' },
}

export const Password: Story = {
  args: { label: 'Password', type: 'password', required: true, placeholder: 'Enter password' },
}
