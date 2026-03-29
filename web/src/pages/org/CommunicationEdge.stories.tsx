import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, Position } from '@xyflow/react'
import { CommunicationEdge, type CommunicationEdgeData } from './CommunicationEdge'

const edgeTypes = { communication: CommunicationEdge }

interface WrapperProps {
  edges: Array<{
    id: string
    source: string
    target: string
    data: CommunicationEdgeData
  }>
}

function Wrapper({ edges }: WrapperProps) {
  const nodes = [
    {
      id: 'a',
      position: { x: 50, y: 100 },
      data: { label: 'Agent A' },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    },
    {
      id: 'b',
      position: { x: 350, y: 100 },
      data: { label: 'Agent B' },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    },
  ]

  const flowEdges = edges.map((e) => ({
    ...e,
    type: 'communication' as const,
  }))

  return (
    <ReactFlowProvider>
      <div className="h-64 w-[500px]">
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          edgeTypes={edgeTypes}
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
  title: 'OrgChart/CommunicationEdge',
  component: Wrapper,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof Wrapper>

export default meta
type Story = StoryObj<typeof meta>

export const LowVolume: Story = {
  args: {
    edges: [
      {
        id: 'e-a-b',
        source: 'a',
        target: 'b',
        data: { volume: 2, frequency: 0.5, maxVolume: 50 },
      },
    ],
  },
}

export const MediumVolume: Story = {
  args: {
    edges: [
      {
        id: 'e-a-b',
        source: 'a',
        target: 'b',
        data: { volume: 25, frequency: 5, maxVolume: 50 },
      },
    ],
  },
}

export const HighVolume: Story = {
  args: {
    edges: [
      {
        id: 'e-a-b',
        source: 'a',
        target: 'b',
        data: { volume: 50, frequency: 15, maxVolume: 50 },
      },
    ],
  },
}

function MultiEdgeWrapper() {
  const nodes = [
    { id: 'a', position: { x: 200, y: 20 }, data: { label: 'Alice' }, sourcePosition: Position.Bottom, targetPosition: Position.Top },
    { id: 'b', position: { x: 50, y: 200 }, data: { label: 'Bob' }, sourcePosition: Position.Right, targetPosition: Position.Left },
    { id: 'c', position: { x: 350, y: 200 }, data: { label: 'Carol' }, sourcePosition: Position.Left, targetPosition: Position.Right },
  ]

  const edges = [
    { id: 'e-a-b', source: 'a', target: 'b', type: 'communication' as const, data: { volume: 40, frequency: 10, maxVolume: 40 } },
    { id: 'e-a-c', source: 'a', target: 'c', type: 'communication' as const, data: { volume: 10, frequency: 2, maxVolume: 40 } },
    { id: 'e-b-c', source: 'b', target: 'c', type: 'communication' as const, data: { volume: 25, frequency: 6, maxVolume: 40 } },
  ]

  return (
    <ReactFlowProvider>
      <div className="h-72 w-[500px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          edgeTypes={edgeTypes}
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

export const MultipleEdges: StoryObj<typeof meta> = {
  args: { edges: [] },
  render: () => <MultiEdgeWrapper />,
}
