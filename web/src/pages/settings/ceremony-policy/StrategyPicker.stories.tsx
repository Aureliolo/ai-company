import type { Meta, StoryObj } from '@storybook/react-vite'
import { StrategyPicker } from './StrategyPicker'

const meta = {
  title: 'Settings/CeremonyPolicy/StrategyPicker',
  component: StrategyPicker,
  tags: ['autodocs'],
} satisfies Meta<typeof StrategyPicker>

export default meta
type Story = StoryObj<typeof meta>

export const TaskDriven: Story = {
  args: { value: 'task_driven', onChange: () => {} },
}

export const Calendar: Story = {
  args: { value: 'calendar', onChange: () => {} },
}

export const Hybrid: Story = {
  args: { value: 'hybrid', onChange: () => {} },
}

export const Disabled: Story = {
  args: { value: 'hybrid', onChange: () => {}, disabled: true },
}
