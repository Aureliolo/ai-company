import type { Meta, StoryObj } from '@storybook/react'
import { ThemeToggle } from './theme-toggle'

const meta = {
  title: 'UI/ThemeToggle',
  component: ThemeToggle,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  decorators: [
    (Story) => (
      <div className="flex h-[500px] w-[400px] items-start justify-end p-8">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ThemeToggle>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
