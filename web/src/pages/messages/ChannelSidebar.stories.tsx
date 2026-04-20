import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { ChannelSidebar } from './ChannelSidebar'
import type { Channel } from '@/api/types/messages'

const channels: Channel[] = [
  { name: '#engineering', type: 'topic', subscribers: [] },
  { name: '#product', type: 'topic', subscribers: [] },
  { name: '#incidents', type: 'topic', subscribers: [] },
  { name: '#dm-alice', type: 'direct', subscribers: [] },
  { name: '#dm-bob', type: 'direct', subscribers: [] },
  { name: '#all-hands', type: 'broadcast', subscribers: [] },
]

const meta: Meta<typeof ChannelSidebar> = {
  title: 'Pages/Messages/ChannelSidebar',
  component: ChannelSidebar,
  parameters: { a11y: { test: 'error' } },
  args: { onSelectChannel: fn(), loading: false },
  decorators: [(Story) => <div className="h-96"><Story /></div>],
}
export default meta

type Story = StoryObj<typeof ChannelSidebar>

export const Default: Story = {
  args: { channels, activeChannel: null, unreadCounts: {} },
}

export const WithActiveChannel: Story = {
  args: { channels, activeChannel: '#engineering', unreadCounts: {} },
}

export const WithUnreadCounts: Story = {
  args: {
    channels,
    activeChannel: '#engineering',
    unreadCounts: { '#product': 5, '#incidents': 2, '#all-hands': 1 },
  },
}

export const Loading: Story = {
  args: { channels: [], activeChannel: null, unreadCounts: {}, loading: true },
}

export const Empty: Story = {
  args: { channels: [], activeChannel: null, unreadCounts: {} },
}
