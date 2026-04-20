import type { Meta, StoryObj } from '@storybook/react-vite'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import { VersionDiffViewer } from './VersionDiffViewer'
import type { WorkflowDiff } from '@/api/types/workflows'

const MOCK_DIFF_WITH_CHANGES: WorkflowDiff = {
  definition_id: 'def-001',
  from_version: 1,
  to_version: 3,
  metadata_changes: [
    { field: 'name', old_value: 'Old Pipeline', new_value: 'New Pipeline' },
    { field: 'description', old_value: 'Old desc', new_value: 'Updated desc' },
  ],
  node_changes: [
    { node_id: 'node-a1', change_type: 'added', old_value: null, new_value: { label: 'Review' } },
    { node_id: 'node-b2', change_type: 'removed', old_value: { label: 'Lint' }, new_value: null },
    { node_id: 'node-c3', change_type: 'moved', old_value: { x: 0, y: 0 }, new_value: { x: 100, y: 200 } },
  ],
  edge_changes: [
    { edge_id: 'edge-x1', change_type: 'added', old_value: null, new_value: { source: 'a', target: 'b' } },
    { edge_id: 'edge-y2', change_type: 'removed', old_value: { source: 'c', target: 'd' }, new_value: null },
  ],
  summary: '2 metadata fields changed, 3 node changes, 2 edge changes',
}

const MOCK_DIFF_EMPTY: WorkflowDiff = {
  definition_id: 'def-001',
  from_version: 2,
  to_version: 3,
  metadata_changes: [],
  node_changes: [],
  edge_changes: [],
  summary: 'No changes detected',
}

const MOCK_DIFF_METADATA_ONLY: WorkflowDiff = {
  definition_id: 'def-001',
  from_version: 1,
  to_version: 2,
  metadata_changes: [
    { field: 'name', old_value: 'Draft', new_value: 'Production Pipeline' },
  ],
  node_changes: [],
  edge_changes: [],
  summary: '1 metadata field changed',
}

function setDiffResult(diff: WorkflowDiff | null) {
  useWorkflowEditorStore.setState({ diffResult: diff })
}

const meta = {
  title: 'Pages/WorkflowEditor/VersionDiffViewer',
  component: VersionDiffViewer,
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof VersionDiffViewer>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  decorators: [
    (Story) => {
      setDiffResult(null)
      return <Story />
    },
  ],
}

export const WithChanges: Story = {
  decorators: [
    (Story) => {
      setDiffResult(MOCK_DIFF_WITH_CHANGES)
      return <Story />
    },
  ],
}

export const EmptyDiff: Story = {
  decorators: [
    (Story) => {
      setDiffResult(MOCK_DIFF_EMPTY)
      return <Story />
    },
  ],
}

export const MetadataOnly: Story = {
  decorators: [
    (Story) => {
      setDiffResult(MOCK_DIFF_METADATA_ONLY)
      return <Story />
    },
  ],
}
