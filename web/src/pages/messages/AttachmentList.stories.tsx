import type { Meta, StoryObj } from '@storybook/react'
import { AttachmentList } from './AttachmentList'

const meta: Meta<typeof AttachmentList> = {
  title: 'Pages/Messages/AttachmentList',
  component: AttachmentList,
  parameters: { a11y: { test: 'error' } },
}
export default meta

type Story = StoryObj<typeof AttachmentList>

export const MixedTypes: Story = {
  args: {
    attachments: [
      { type: 'artifact', ref: 'pr-42' },
      { type: 'file', ref: 'report.pdf' },
      { type: 'link', ref: 'https://example.com' },
    ],
  },
}

export const SingleArtifact: Story = {
  args: {
    attachments: [{ type: 'artifact', ref: 'pr-123' }],
  },
}

export const Empty: Story = {
  args: { attachments: [] },
}
