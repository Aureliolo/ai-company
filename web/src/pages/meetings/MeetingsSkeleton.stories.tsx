import type { Meta, StoryObj } from '@storybook/react'
import { MeetingsSkeleton } from './MeetingsSkeleton'

const meta = {
  title: 'Meetings/MeetingsSkeleton',
  component: MeetingsSkeleton,
  tags: ['autodocs'],
} satisfies Meta<typeof MeetingsSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
