import type { Meta, StoryObj } from '@storybook/react'
import { TokenUsageBar } from './token-usage-bar'

const meta = {
  title: 'UI/TokenUsageBar',
  component: TokenUsageBar,
  tags: ['autodocs'],
} satisfies Meta<typeof TokenUsageBar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    segments: [
      { label: 'agent-alice', value: 350 },
      { label: 'agent-bob', value: 300 },
    ],
    total: 2000,
  },
}

export const SingleSegment: Story = {
  args: {
    segments: [{ label: 'agent-alice', value: 650 }],
    total: 2000,
  },
}

export const Full: Story = {
  args: {
    segments: [
      { label: 'agent-alice', value: 1200 },
      { label: 'agent-bob', value: 800 },
    ],
    total: 2000,
  },
}

export const Overflow: Story = {
  args: {
    segments: [
      { label: 'agent-alice', value: 1500 },
      { label: 'agent-bob', value: 800 },
    ],
    total: 2000,
  },
}

export const Empty: Story = {
  args: {
    segments: [],
    total: 2000,
  },
}

export const ManyParticipants: Story = {
  args: {
    segments: [
      { label: 'agent-alice', value: 350 },
      { label: 'agent-bob', value: 300 },
      { label: 'agent-carol', value: 280 },
      { label: 'agent-dave', value: 150 },
      { label: 'agent-eve', value: 120 },
    ],
    total: 5000,
  },
}

export const CustomColors: Story = {
  args: {
    segments: [
      { label: 'Input', value: 380, color: 'bg-accent' },
      { label: 'Output', value: 270, color: 'bg-success' },
    ],
    total: 2000,
  },
}
