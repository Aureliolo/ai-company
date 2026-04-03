import type { Meta, StoryObj } from '@storybook/react-vite'
import { StrategyChangeWarning } from './StrategyChangeWarning'

const meta = {
  title: 'Settings/CeremonyPolicy/StrategyChangeWarning',
  component: StrategyChangeWarning,
  tags: ['autodocs'],
} satisfies Meta<typeof StrategyChangeWarning>

export default meta
type Story = StoryObj<typeof meta>

export const TaskToCalendar: Story = {
  args: {
    currentStrategy: 'calendar',
    activeStrategy: 'task_driven',
  },
}

export const CalendarToHybrid: Story = {
  args: {
    currentStrategy: 'hybrid',
    activeStrategy: 'calendar',
  },
}

export const SameStrategy: Story = {
  args: {
    currentStrategy: 'task_driven',
    activeStrategy: 'task_driven',
  },
}
