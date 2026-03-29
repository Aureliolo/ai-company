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

export const Healthy: Story = {
  args: {
    data: {
      departmentName: 'engineering',
      displayName: 'Engineering',
      healthPercent: 92,
      agentCount: 5,
      activeCount: 4,
      taskCount: 12,
      costUsd: 45.8,
    },
  },
}

export const Warning: Story = {
  args: {
    data: {
      departmentName: 'product',
      displayName: 'Product',
      healthPercent: 45,
      agentCount: 3,
      activeCount: 1,
      taskCount: 8,
      costUsd: 22.3,
    },
  },
}

export const Critical: Story = {
  args: {
    data: {
      departmentName: 'operations',
      displayName: 'Operations',
      healthPercent: 15,
      agentCount: 2,
      activeCount: 0,
      taskCount: 3,
      costUsd: null,
    },
  },
}

export const DropTargetActive: Story = {
  args: {
    data: {
      departmentName: 'engineering',
      displayName: 'Engineering',
      healthPercent: 85,
      agentCount: 5,
      activeCount: 3,
      taskCount: 10,
      costUsd: 38.5,
      isDropTarget: true,
    },
  },
}
