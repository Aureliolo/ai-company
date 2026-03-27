import type { Meta, StoryObj } from '@storybook/react'
import { ApprovalsSkeleton } from './ApprovalsSkeleton'

const meta: Meta<typeof ApprovalsSkeleton> = {
  title: 'Pages/Approvals/ApprovalsSkeleton',
  component: ApprovalsSkeleton,
  parameters: {
    a11y: { test: 'error' },
  },
}
export default meta

type Story = StoryObj<typeof ApprovalsSkeleton>

export const Default: Story = {}
