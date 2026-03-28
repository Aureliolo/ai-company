import type { Meta, StoryObj } from '@storybook/react'
import { MeetingFilterBar } from './MeetingFilterBar'

const meta = {
  title: 'Meetings/MeetingFilterBar',
  component: MeetingFilterBar,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingFilterBar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    filters: {},
    onFiltersChange: () => {},
    meetingTypes: ['daily_standup', 'sprint_planning', 'code_review'],
  },
}

export const WithActiveFilters: Story = {
  args: {
    filters: { status: 'completed', meetingType: 'daily_standup' },
    onFiltersChange: () => {},
    meetingTypes: ['daily_standup', 'sprint_planning', 'code_review'],
  },
}
