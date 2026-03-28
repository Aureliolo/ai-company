import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { MeetingTimelineNode } from './MeetingTimelineNode'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingTimelineNode',
  component: MeetingTimelineNode,
  tags: ['autodocs'],
  decorators: [(Story) => <MemoryRouter><Story /></MemoryRouter>],
} satisfies Meta<typeof MeetingTimelineNode>

export default meta
type Story = StoryObj<typeof meta>

export const Completed: Story = {
  args: { meeting: makeMeeting('1', { status: 'completed' }) },
}

export const InProgress: Story = {
  args: { meeting: makeMeeting('2', { status: 'in_progress', meeting_type_name: 'sprint_planning' }) },
}

export const Scheduled: Story = {
  args: { meeting: makeMeeting('3', { status: 'scheduled', meeting_type_name: 'code_review' }) },
}

export const Failed: Story = {
  args: { meeting: makeMeeting('4', { status: 'failed' }) },
}

export const Cancelled: Story = {
  args: { meeting: makeMeeting('5', { status: 'cancelled' }) },
}

export const BudgetExhausted: Story = {
  args: { meeting: makeMeeting('6', { status: 'budget_exhausted' }) },
}
