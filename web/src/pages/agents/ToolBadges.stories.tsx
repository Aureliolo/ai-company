import type { Meta, StoryObj } from '@storybook/react'
import { ToolBadges } from './ToolBadges'

const meta = {
  title: 'Agents/ToolBadges',
  component: ToolBadges,
  decorators: [(Story) => <div className="p-6 max-w-lg"><Story /></div>],
} satisfies Meta<typeof ToolBadges>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { tools: ['file_system', 'git', 'code_execution', 'web_search', 'terminal'] },
}

export const SingleTool: Story = {
  args: { tools: ['git'] },
}

export const Empty: Story = {
  args: { tools: [] },
}
