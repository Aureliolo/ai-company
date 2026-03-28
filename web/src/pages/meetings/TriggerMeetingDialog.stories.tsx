import type { Meta, StoryObj } from '@storybook/react'
import { TriggerMeetingDialog } from './TriggerMeetingDialog'

const meta = {
  title: 'Meetings/TriggerMeetingDialog',
  component: TriggerMeetingDialog,
  tags: ['autodocs'],
} satisfies Meta<typeof TriggerMeetingDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    onConfirm: async () => {},
  },
}

export const Loading: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    onConfirm: async () => {},
    loading: true,
  },
}
