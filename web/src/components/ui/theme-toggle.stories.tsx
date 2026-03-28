import { useEffect } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { useThemeStore } from '@/stores/theme'
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

function PopoverOpenDecorator({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    useThemeStore.getState().setPopoverOpen(true)
  }, [])
  return <>{children}</>
}

export const PopoverOpen: Story = {
  decorators: [
    (Story) => (
      <PopoverOpenDecorator>
        <Story />
      </PopoverOpenDecorator>
    ),
  ],
}
