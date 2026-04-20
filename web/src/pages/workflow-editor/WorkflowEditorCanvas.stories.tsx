import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { ReactFlowProvider, type Edge, type Node } from '@xyflow/react'
import { WorkflowEditorCanvas } from './WorkflowEditorCanvas'

const nodeTypes = {}
const edgeTypes = {}

const sampleNodes: Node[] = [
  { id: 'start', type: 'start', position: { x: 0, y: 0 }, data: { label: 'Start' } },
  { id: 'task-1', type: 'task', position: { x: 200, y: 0 }, data: { label: 'Generate draft' } },
  { id: 'end', type: 'end', position: { x: 400, y: 0 }, data: { label: 'End' } },
]

const sampleEdges: Edge[] = [
  { id: 'e1', source: 'start', target: 'task-1', type: 'sequential' },
  { id: 'e2', source: 'task-1', target: 'end', type: 'sequential' },
]

const meta = {
  title: 'Pages/WorkflowEditor/Canvas',
  component: WorkflowEditorCanvas,
  decorators: [
    (Story) => (
      <div style={{ width: '100%', height: 'calc(100vh - 4rem)' }}>
        <ReactFlowProvider>
          <Story />
        </ReactFlowProvider>
      </div>
    ),
  ],
  args: {
    nodeTypes,
    edgeTypes,
    defaultViewport: undefined,
    onNodeClick: fn(),
    onPaneClick: fn(),
    onConnect: fn(),
    onNodesChange: fn(),
    onEdgesChange: fn(),
    onMoveEnd: fn(),
  },
} satisfies Meta<typeof WorkflowEditorCanvas>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    nodes: sampleNodes,
    edges: sampleEdges,
  },
}

export const Empty: Story = {
  args: {
    nodes: [],
    edges: [],
  },
}
