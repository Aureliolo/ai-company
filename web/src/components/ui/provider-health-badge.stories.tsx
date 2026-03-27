import type { Meta, StoryObj } from '@storybook/react-vite'
import { ProviderHealthBadge } from './provider-health-badge'

const meta = {
  title: 'UI/ProviderHealthBadge',
  component: ProviderHealthBadge,
  tags: ['autodocs'],
  parameters: { a11y: { test: 'error' } },
} satisfies Meta<typeof ProviderHealthBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Up: Story = { args: { status: 'up', label: true } }
export const Degraded: Story = { args: { status: 'degraded', label: true } }
export const Down: Story = { args: { status: 'down', label: true } }
export const DotOnly: Story = { args: { status: 'up' } }
export const WithPulse: Story = { args: { status: 'degraded', label: true, pulse: true } }

export const AllStates: Story = {
  args: { status: 'up', label: true },
  render: () => (
    <div className="flex flex-col gap-3">
      <ProviderHealthBadge status="up" label />
      <ProviderHealthBadge status="degraded" label />
      <ProviderHealthBadge status="down" label />
      <ProviderHealthBadge status="up" />
    </div>
  ),
}
