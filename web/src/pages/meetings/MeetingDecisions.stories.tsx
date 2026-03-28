import type { Meta, StoryObj } from '@storybook/react'
import { MeetingDecisions } from './MeetingDecisions'

const meta = {
  title: 'Meetings/MeetingDecisions',
  component: MeetingDecisions,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingDecisions>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    decisions: [
      'Adopt modular monolith architecture for the billing service',
      'Schedule follow-up design review in two weeks',
      'Assign security audit to the operations team',
    ],
  },
}

export const SingleDecision: Story = {
  args: {
    decisions: ['Continue current sprint tasks'],
  },
}

export const Empty: Story = {
  args: { decisions: [] },
}
