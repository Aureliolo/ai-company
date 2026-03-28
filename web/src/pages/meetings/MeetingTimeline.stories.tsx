import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { MeetingTimeline } from './MeetingTimeline'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingTimeline',
  component: MeetingTimeline,
  tags: ['autodocs'],
  decorators: [(Story) => <MemoryRouter><Story /></MemoryRouter>],
} satisfies Meta<typeof MeetingTimeline>

export default meta
type Story = StoryObj<typeof meta>

export const FewMeetings: Story = {
  args: {
    meetings: [
      makeMeeting('1', { status: 'completed', meeting_type_name: 'daily_standup' }),
      makeMeeting('2', { status: 'in_progress', meeting_type_name: 'sprint_planning' }),
      makeMeeting('3', { status: 'scheduled', meeting_type_name: 'code_review' }),
    ],
  },
}

export const ManyMeetings: Story = {
  args: {
    meetings: Array.from({ length: 12 }, (_, i) =>
      makeMeeting(`m-${i}`, {
        status: i === 0 ? 'in_progress' : 'completed',
        meeting_type_name: ['daily_standup', 'sprint_planning', 'code_review'][i % 3]!,
      }),
    ),
  },
}

export const SingleMeeting: Story = {
  args: {
    meetings: [makeMeeting('1')],
  },
}

export const Empty: Story = {
  args: { meetings: [] },
}
