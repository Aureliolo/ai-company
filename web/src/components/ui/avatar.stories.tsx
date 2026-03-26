import type { Meta, StoryObj } from '@storybook/react'
import { Avatar } from './avatar'

const meta = {
  title: 'UI/Avatar',
  component: Avatar,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
  },
} satisfies Meta<typeof Avatar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { name: 'Alice Smith' },
}

export const SingleName: Story = {
  args: { name: 'Alice' },
}

export const ThreeWordName: Story = {
  args: { name: 'Alice Marie Smith' },
}

export const Small: Story = {
  args: { name: 'Alice Smith', size: 'sm' },
}

export const Large: Story = {
  args: { name: 'Alice Smith', size: 'lg' },
}

export const AllSizes: Story = {
  args: { name: 'Alice Smith' },
  render: () => (
    <div className="flex items-center gap-3">
      <Avatar name="Alice Smith" size="sm" />
      <Avatar name="Alice Smith" size="md" />
      <Avatar name="Alice Smith" size="lg" />
    </div>
  ),
}
