import type { Meta, StoryObj } from '@storybook/react'
import { MeetingTokenBreakdown } from './MeetingTokenBreakdown'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingTokenBreakdown',
  component: MeetingTokenBreakdown,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingTokenBreakdown>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { meeting: makeMeeting('1') },
}

export const ManyParticipants: Story = {
  args: {
    meeting: makeMeeting('2', {
      token_usage_by_participant: {
        'agent-alice': 400,
        'agent-bob': 350,
        'agent-carol': 280,
        'agent-dave': 150,
        'agent-eve': 120,
      },
      contribution_rank: ['agent-alice', 'agent-bob', 'agent-carol', 'agent-dave', 'agent-eve'],
      token_budget: 5000,
    }),
  },
}

export const HighUsage: Story = {
  args: { meeting: makeMeeting('3', { token_budget: 700 }) },
}
