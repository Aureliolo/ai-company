import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { MeetingDetailHeader } from './MeetingDetailHeader'
import { makeMeeting } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Meetings/MeetingDetailHeader',
  component: MeetingDetailHeader,
  tags: ['autodocs'],
  decorators: [(Story) => <MemoryRouter><Story /></MemoryRouter>],
} satisfies Meta<typeof MeetingDetailHeader>

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
