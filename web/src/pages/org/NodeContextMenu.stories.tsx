import type { Meta, StoryObj } from '@storybook/react'
import { NodeContextMenu } from './NodeContextMenu'

const meta = {
  title: 'OrgChart/NodeContextMenu',
  component: NodeContextMenu,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
  decorators: [
    (Story) => (
      <div style={{ height: 300, position: 'relative' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof NodeContextMenu>

export default meta
type Story = StoryObj<typeof meta>

export const AgentMenu: Story = {
  args: {
    nodeId: 'agent-1',
    nodeType: 'agent',
    position: { x: 100, y: 50 },
    onClose: () => {},
  },
}

export const DepartmentMenu: Story = {
  args: {
    nodeId: 'dept-engineering',
    nodeType: 'department',
    position: { x: 100, y: 50 },
    onClose: () => {},
  },
}

export const CeoMenu: Story = {
  args: {
    nodeId: 'ceo-1',
    nodeType: 'ceo',
    position: { x: 100, y: 50 },
    onClose: () => {},
  },
}
