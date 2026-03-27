import type { Meta, StoryObj } from '@storybook/react'
import { OrgEditSkeleton } from './OrgEditSkeleton'

const meta = {
  title: 'OrgEdit/OrgEditSkeleton',
  component: OrgEditSkeleton,
} satisfies Meta<typeof OrgEditSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
