import type { Meta, StoryObj } from '@storybook/react-vite'
import { ConnectionHealthBadge } from './connection-health-badge'

const meta = {
  title: 'Components/ConnectionHealthBadge',
  component: ConnectionHealthBadge,
  tags: ['autodocs'],
} satisfies Meta<typeof ConnectionHealthBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Healthy: Story = { args: { status: 'healthy', label: true } }
export const Degraded: Story = { args: { status: 'degraded', label: true } }
export const Unhealthy: Story = { args: { status: 'unhealthy', label: true } }
export const Unknown: Story = { args: { status: 'unknown', label: true } }
export const DotOnly: Story = { args: { status: 'healthy' } }
export const Pulsing: Story = { args: { status: 'degraded', label: true, pulse: true } }
