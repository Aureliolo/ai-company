import type { Meta, StoryObj } from '@storybook/react'
import { MeetingDetailSkeleton } from './MeetingDetailSkeleton'

const meta = {
  title: 'Meetings/MeetingDetailSkeleton',
  component: MeetingDetailSkeleton,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingDetailSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
