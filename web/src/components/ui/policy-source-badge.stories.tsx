import type { Meta, StoryObj } from '@storybook/react-vite'
import { PolicySourceBadge } from './policy-source-badge'

const meta = {
  title: 'UI/PolicySourceBadge',
  component: PolicySourceBadge,
  tags: ['autodocs'],
} satisfies Meta<typeof PolicySourceBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Project: Story = {
  args: { source: 'project' },
}

export const Department: Story = {
  args: { source: 'department' },
}

export const Default: Story = {
  args: { source: 'default' },
}
