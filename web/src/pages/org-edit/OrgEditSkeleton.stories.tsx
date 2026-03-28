import type { Meta, StoryObj } from '@storybook/react'
import { OrgEditSkeleton } from './OrgEditSkeleton'

const meta = {
  title: 'OrgEdit/OrgEditSkeleton',
  component: OrgEditSkeleton,
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof OrgEditSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
