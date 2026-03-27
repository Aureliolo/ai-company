import type { Meta, StoryObj } from '@storybook/react'
import { OrgChartSkeleton } from './OrgChartSkeleton'

const meta = {
  title: 'OrgChart/OrgChartSkeleton',
  component: OrgChartSkeleton,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
  decorators: [
    (Story) => (
      <div style={{ height: 400 }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof OrgChartSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
