import type { Meta, StoryObj } from '@storybook/react'
import { SubworkflowCard } from './SubworkflowCard'
import type { SubworkflowSummary } from '@/api/types/workflows'
import { fn } from 'storybook/test'

const meta: Meta<typeof SubworkflowCard> = {
  title: 'Subworkflows/Subworkflow Card',
  component: SubworkflowCard,
  parameters: { layout: 'centered' },
  args: { onClick: fn() },
}

export default meta

type Story = StoryObj<typeof SubworkflowCard>

const baseSub: SubworkflowSummary = {
  subworkflow_id: 'sub-quarterly-close',
  latest_version: '2.1.0',
  name: 'Quarterly Close',
  description: 'Finance quarterly close workflow with multi-step validation.',
  input_count: 3,
  output_count: 2,
  version_count: 4,
}

export const Default: Story = {
  args: { subworkflow: baseSub },
}

export const NoDescription: Story = {
  args: {
    subworkflow: { ...baseSub, description: '' },
  },
}

export const SingleVersion: Story = {
  args: {
    subworkflow: {
      ...baseSub,
      latest_version: '1.0.0',
      version_count: 1,
      name: 'Simple Greeting',
      description: 'Greets a user by name.',
    },
  },
}

export const ManyInputsOutputs: Story = {
  args: {
    subworkflow: {
      ...baseSub,
      input_count: 12,
      output_count: 8,
      name: 'Data Pipeline',
    },
  },
}
