import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { WorkflowEditorSidebar } from './WorkflowEditorSidebar'

const meta = {
  title: 'Pages/WorkflowEditor/Sidebar',
  component: WorkflowEditorSidebar,
  args: {
    onNodeDrawerClose: fn(),
    onConfigChange: fn(),
    onVersionHistoryClose: fn(),
  },
} satisfies Meta<typeof WorkflowEditorSidebar>

export default meta
type Story = StoryObj<typeof meta>

export const Closed: Story = {
  args: {
    nodeDrawerOpen: false,
    selectedNodeId: null,
    selectedNodeType: null,
    selectedNodeLabel: '',
    selectedNodeConfig: {},
    versionHistoryOpen: false,
  },
}

export const NodeDrawerOpen: Story = {
  args: {
    nodeDrawerOpen: true,
    selectedNodeId: 'task-1',
    selectedNodeType: 'task',
    selectedNodeLabel: 'Generate draft',
    selectedNodeConfig: { agent_role: 'engineer' },
    versionHistoryOpen: false,
  },
}

export const VersionHistoryOpen: Story = {
  args: {
    nodeDrawerOpen: false,
    selectedNodeId: null,
    selectedNodeType: null,
    selectedNodeLabel: '',
    selectedNodeConfig: {},
    versionHistoryOpen: true,
  },
}
