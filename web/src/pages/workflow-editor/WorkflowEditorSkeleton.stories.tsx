import type { Meta, StoryObj } from '@storybook/react'
import { WorkflowEditorSkeleton } from './WorkflowEditorSkeleton'

const meta: Meta = {
  title: 'Workflow Editor/Skeleton',
  parameters: { layout: 'padded' },
}

export default meta

export const Default: StoryObj = {
  render: () => (
    <div className="h-[60vh]">
      <WorkflowEditorSkeleton />
    </div>
  ),
}
