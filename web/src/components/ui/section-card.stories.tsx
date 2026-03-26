import type { Meta, StoryObj } from '@storybook/react'
import { Settings } from 'lucide-react'
import { SectionCard } from './section-card'
import { Button } from './button'

const meta = {
  title: 'UI/SectionCard',
  component: SectionCard,
  tags: ['autodocs'],
} satisfies Meta<typeof SectionCard>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    title: 'Overview',
    children: 'Section content goes here.',
  },
}

export const WithIcon: Story = {
  args: {
    title: 'Settings',
    icon: Settings,
    children: 'Settings content goes here.',
  },
}

export const WithAction: Story = {
  args: {
    title: 'Agents',
    action: <Button size="xs" variant="ghost">View All</Button>,
    children: 'Agent list would appear here.',
  },
}

export const WithIconAndAction: Story = {
  args: {
    title: 'Settings',
    icon: Settings,
    action: <Button size="xs" variant="ghost">Edit</Button>,
    children: 'Settings content goes here.',
  },
}

export const NestedContent: Story = {
  args: { title: 'Department Health', children: null },
  render: () => (
    <SectionCard title="Department Health">
      <div className="flex flex-col gap-3 text-sm text-text-secondary">
        <p>Engineering: 92%</p>
        <p>Marketing: 78%</p>
        <p>Sales: 65%</p>
      </div>
    </SectionCard>
  ),
}
