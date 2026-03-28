import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { MeetingCard } from './MeetingCard'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingCard',
  component: MeetingCard,
  tags: ['autodocs'],
  decorators: [(Story) => <MemoryRouter><div className="max-w-md"><Story /></div></MemoryRouter>],
} satisfies Meta<typeof MeetingCard>

export default meta
type Story = StoryObj<typeof meta>

export const Completed: Story = {
  args: { meeting: makeMeeting('1') },
}

export const InProgress: Story = {
  args: { meeting: makeMeeting('2', { status: 'in_progress', meeting_type_name: 'sprint_planning' }) },
}

export const Failed: Story = {
  args: { meeting: makeMeeting('3', { status: 'failed', error_message: 'Token budget exceeded' }) },
}

export const NoMinutes: Story = {
  args: { meeting: makeMeeting('4', { status: 'scheduled', minutes: null, meeting_duration_seconds: null }) },
}

export const HighTokenUsage: Story = {
  args: { meeting: makeMeeting('5', { token_budget: 700 }) },
}
