import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { MessageFilterBar } from './MessageFilterBar'

const meta: Meta<typeof MessageFilterBar> = {
  title: 'Pages/Messages/MessageFilterBar',
  component: MessageFilterBar,
  parameters: { a11y: { test: 'error' } },
  args: { onFiltersChange: fn(), totalCount: 42 },
  decorators: [(Story) => <div className="max-w-2xl"><Story /></div>],
}
export default meta

type Story = StoryObj<typeof MessageFilterBar>

export const NoFilters: Story = {
  args: { filters: {} },
}

export const WithTypeFilter: Story = {
  args: { filters: { type: 'delegation' }, filteredCount: 8 },
}

export const WithMultipleFilters: Story = {
  args: {
    filters: { type: 'task_update', priority: 'high', search: 'auth' },
    filteredCount: 3,
  },
}

export const WithSearchOnly: Story = {
  args: { filters: { search: 'production' }, filteredCount: 5 },
}
