import type { Meta, StoryObj } from '@storybook/react'
import { MeetingMetricCards } from './MeetingMetricCards'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingMetricCards',
  component: MeetingMetricCards,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingMetricCards>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    meetings: [
      makeMeeting('1', { status: 'completed' }),
      makeMeeting('2', { status: 'in_progress' }),
      makeMeeting('3', { status: 'completed' }),
      makeMeeting('4', { status: 'failed' }),
    ],
  },
}

export const Empty: Story = {
  args: { meetings: [] },
}
