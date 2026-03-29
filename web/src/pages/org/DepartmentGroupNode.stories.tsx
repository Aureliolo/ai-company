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
      cost7d: 45.8,
      currency: 'EUR',
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
      cost7d: 22.3,
      currency: 'EUR',
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
      cost7d: null,
      currency: null,
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
      cost7d: 38.5,
      currency: 'EUR',
      isDropTarget: true,
    },
  },
}
