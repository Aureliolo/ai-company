import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider } from '@xyflow/react'
import { DeptAdminNode } from './DeptAdminNode'
import type { DeptAdminNodeData } from './DeptAdminNode'

const nodeTypes = { deptAdmin: DeptAdminNode }

function Wrapper({ data }: { data: DeptAdminNodeData }) {
  return (
    <ReactFlowProvider>
      <div style={{ width: 400, height: 200 }}>
        <ReactFlow
          nodes={[
            {
              id: '1',
              type: 'deptAdmin',
              position: { x: 80, y: 40 },
              data,
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
  title: 'OrgChart/DeptAdminNode',
  component: Wrapper,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof Wrapper>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    data: {
      adminId: 'admin-1',
      displayName: 'Jane Cooper',
      department: 'engineering',
      role: 'department_admin',
    },
  },
}

export const LongName: Story = {
  args: {
    data: {
      adminId: 'admin-2',
      displayName: 'Alexandrina von Humboldtstein',
      department: 'research-and-development',
      role: 'department_admin',
    },
  },
}
