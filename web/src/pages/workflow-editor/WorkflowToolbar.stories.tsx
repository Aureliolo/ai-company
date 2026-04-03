import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlowProvider } from '@xyflow/react'
import { WorkflowToolbar } from './WorkflowToolbar'

const noop = () => {}
const noopAsync = async () => {}

function Wrapper(props: Partial<React.ComponentProps<typeof WorkflowToolbar>>) {
  return (
    <ReactFlowProvider>
      <WorkflowToolbar
        onAddNode={noop}
        onUndo={noop}
        onRedo={noop}
        onSave={noopAsync}
        onValidate={noopAsync}
        onExport={noopAsync}
        canUndo={false}
        canRedo={false}
        dirty={false}
        saving={false}
        validating={false}
        validationValid={null}
        {...props}
      />
    </ReactFlowProvider>
  )
}

const meta: Meta = {
  title: 'Workflow Editor/Toolbar',
  component: WorkflowToolbar,
  parameters: { layout: 'padded' },
}

export default meta

export const Default: StoryObj = {
  render: () => <Wrapper />,
}

export const Dirty: StoryObj = {
  render: () => <Wrapper dirty canUndo canRedo />,
}

export const Saving: StoryObj = {
  render: () => <Wrapper dirty saving />,
}

export const ValidationPassed: StoryObj = {
  render: () => <Wrapper validationValid />,
}

export const ValidationFailed: StoryObj = {
  render: () => <Wrapper validationValid={false} />,
}
