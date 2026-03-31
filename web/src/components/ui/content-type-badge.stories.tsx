import type { Meta, StoryObj } from '@storybook/react'
import { ContentTypeBadge } from './content-type-badge'

const meta = {
  title: 'UI/ContentTypeBadge',
  component: ContentTypeBadge,
  tags: ['autodocs'],
} satisfies Meta<typeof ContentTypeBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Json: Story = {
  args: { contentType: 'application/json' },
}

export const Pdf: Story = {
  args: { contentType: 'application/pdf' },
}

export const Image: Story = {
  args: { contentType: 'image/png' },
}

export const Text: Story = {
  args: { contentType: 'text/plain' },
}

export const Markdown: Story = {
  args: { contentType: 'text/markdown' },
}

export const Csv: Story = {
  args: { contentType: 'text/csv' },
}

export const Binary: Story = {
  args: { contentType: 'application/octet-stream' },
}

export const AllTypes: Story = {
  args: { contentType: 'text/plain' },
  render: () => (
    <div className="flex flex-wrap gap-2">
      <ContentTypeBadge contentType="application/json" />
      <ContentTypeBadge contentType="application/pdf" />
      <ContentTypeBadge contentType="image/png" />
      <ContentTypeBadge contentType="text/plain" />
      <ContentTypeBadge contentType="text/markdown" />
      <ContentTypeBadge contentType="text/csv" />
      <ContentTypeBadge contentType="application/octet-stream" />
    </div>
  ),
}
