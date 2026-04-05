import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider } from '@xyflow/react'
import { DepartmentGroupNode } from './DepartmentGroupNode'
import type { DepartmentGroupData } from './build-org-tree'

const nodeTypes = { department: DepartmentGroupNode }

function Wrapper({ data }: { data: DepartmentGroupData }) {
  return (
    <ReactFlowProvider>
      <div style={{ width: 500, height: 200 }}>
        <ReactFlow
          nodes={[
            {
              id: '1',
              type: 'department',
              position: { x: 20, y: 20 },
              data,
              style: { width: 400, height: 150 },
            },
          ]}
          edges={[]}
          nodeTypes={nodeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          zoomOnScroll={false}
          panOnDrag={false}
        />
      </div>
    </ReactFlowProvider>
  )
}

const meta = {
  title: 'OrgChart/DepartmentGroupNode',
  component: Wrapper,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof Wrapper>

export default meta
type Story = StoryObj<typeof meta>

export const Populated: Story = {
  args: {
    data: {
      departmentName: 'engineering',
      displayName: 'Engineering',
      agentCount: 5,
      activeCount: 4,
      budgetPercent: 40,
      utilizationPercent: 60,
      cost7d: 45.8,
      currency: 'EUR',
      statusDots: [
        { agentId: 'a1', runtimeStatus: 'active' },
        { agentId: 'a2', runtimeStatus: 'active' },
        { agentId: 'a3', runtimeStatus: 'active' },
        { agentId: 'a4', runtimeStatus: 'idle' },
        { agentId: 'a5', runtimeStatus: 'idle' },
      ],
      isEmpty: false,
    },
  },
}

export const OverBudget: Story = {
  args: {
    data: {
      departmentName: 'product',
      displayName: 'Product',
      agentCount: 3,
      activeCount: 1,
      budgetPercent: 120,
      utilizationPercent: 95,
      cost7d: 22.3,
      currency: 'EUR',
      statusDots: [
        { agentId: 'p1', runtimeStatus: 'active' },
        { agentId: 'p2', runtimeStatus: 'error' },
        { agentId: 'p3', runtimeStatus: 'idle' },
      ],
      isEmpty: false,
    },
  },
}

export const EmptyDepartment: Story = {
  args: {
    data: {
      departmentName: 'security',
      displayName: 'Security',
      agentCount: 0,
      activeCount: 0,
      budgetPercent: 8,
      utilizationPercent: null,
      cost7d: null,
      currency: null,
      statusDots: [],
      isEmpty: true,
    },
  },
}

export const DropTargetActive: Story = {
  args: {
    data: {
      departmentName: 'engineering',
      displayName: 'Engineering',
      agentCount: 5,
      activeCount: 3,
      budgetPercent: 40,
      utilizationPercent: 70,
      cost7d: 38.5,
      currency: 'EUR',
      statusDots: [
        { agentId: 'a1', runtimeStatus: 'active' },
        { agentId: 'a2', runtimeStatus: 'active' },
        { agentId: 'a3', runtimeStatus: 'active' },
        { agentId: 'a4', runtimeStatus: 'idle' },
        { agentId: 'a5', runtimeStatus: 'idle' },
      ],
      isEmpty: false,
      isDropTarget: true,
    },
  },
}
