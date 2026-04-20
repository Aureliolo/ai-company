import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { MessageDetailDrawer } from './MessageDetailDrawer'
import type { Message } from '@/api/types/messages'

const fullMessage: Message = {
  id: 'msg-1',
  timestamp: '2026-03-28T10:30:00Z',
  sender: 'sarah_chen',
  to: '#engineering',
  type: 'task_update',
  priority: 'normal',
  channel: '#engineering',
  content: 'Completed API endpoint for user authentication. All tests pass, coverage at 95%. PR ready for review.\n\nKey changes:\n- Added JWT validation middleware\n- Created user session store\n- Updated OpenAPI schema',
  attachments: [
    { type: 'artifact', ref: 'pr-42' },
    { type: 'file', ref: 'coverage-report.html' },
  ],
  metadata: {
    task_id: 'task-123',
    project_id: 'proj-456',
    tokens_used: 1200,
    cost: 0.018,
    extra: [['model', 'test-medium-001'], ['latency_ms', '2340']],
  },
}

const meta: Meta<typeof MessageDetailDrawer> = {
  title: 'Pages/Messages/MessageDetailDrawer',
  component: MessageDetailDrawer,
  parameters: { a11y: { test: 'error' } },
  args: { onClose: fn() },
}
export default meta

type Story = StoryObj<typeof MessageDetailDrawer>

export const FullMetadata: Story = {
  args: { message: fullMessage, open: true },
}

export const MinimalMetadata: Story = {
  args: {
    message: {
      ...fullMessage,
      attachments: [],
      metadata: { task_id: null, project_id: null, tokens_used: null, cost: null, extra: [] },
    },
    open: true,
  },
}

export const WithAttachments: Story = {
  args: {
    message: {
      ...fullMessage,
      metadata: {
        task_id: null,
        project_id: null,
        tokens_used: null,
        cost: null,
        extra: [],
      },
      attachments: [
        { type: 'artifact', ref: 'pr-42' },
        { type: 'file', ref: 'coverage-report.html' },
        { type: 'link', ref: 'https://example.com/docs' },
      ],
    },
    open: true,
  },
}

export const Closed: Story = {
  args: { message: null, open: false },
}
