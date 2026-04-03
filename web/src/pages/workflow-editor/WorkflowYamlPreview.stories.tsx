import type { Meta, StoryObj } from '@storybook/react'
import { WorkflowYamlPreview } from './WorkflowYamlPreview'

const sampleYaml = `workflow_definition:
  name: Feature Pipeline
  workflow_type: sequential_pipeline
  steps:
    - id: task-1
      type: task
      title: Design API
    - id: task-2
      type: task
      title: Implement
      depends_on:
        - task-1
`

const meta: Meta<typeof WorkflowYamlPreview> = {
  title: 'Workflow Editor/YAML Preview',
  component: WorkflowYamlPreview,
  parameters: { layout: 'padded' },
}

export default meta

export const Default: StoryObj<typeof WorkflowYamlPreview> = {
  render: () => <WorkflowYamlPreview yaml={sampleYaml} />,
}

export const Empty: StoryObj<typeof WorkflowYamlPreview> = {
  render: () => <WorkflowYamlPreview yaml="" />,
}
