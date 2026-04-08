import type { Meta, StoryObj } from '@storybook/react'
import { TaskStatusIndicator, PriorityBadge } from './task-status-indicator'
import type { Priority, TaskStatus } from '@/api/types'

// ── TaskStatusIndicator ─────────────────────────────────────

const statusMeta = {
  title: 'UI/TaskStatusIndicator',
  component: TaskStatusIndicator,
  tags: ['autodocs'],
} satisfies Meta<typeof TaskStatusIndicator>

export default statusMeta
type StatusStory = StoryObj<typeof statusMeta>

const ALL_STATUSES: TaskStatus[] = [
  'created', 'assigned', 'in_progress', 'in_review', 'completed',
  'blocked', 'failed', 'interrupted', 'suspended', 'cancelled',
]

export const Default: StatusStory = {
  args: { status: 'in_progress' },
}

export const WithLabel: StatusStory = {
  args: { status: 'in_progress', label: true },
}

export const Pulsing: StatusStory = {
  args: { status: 'in_progress', label: true, pulse: true },
}

export const AllStatuses: StatusStory = {
  args: { status: 'created', label: true },
  render: () => (
    <div className="flex flex-col gap-2">
      {ALL_STATUSES.map((status) => (
        <TaskStatusIndicator key={status} status={status} label />
      ))}
    </div>
  ),
}

// ── PriorityBadge ───────────────────────────────────────────
// PriorityBadges uses a custom render that ignores args -- it showcases all 4 priority levels.

export const PriorityBadges: StatusStory = {
  args: { status: 'created' },
  render: () => (
    <div className="flex gap-2">
      {(['critical', 'high', 'medium', 'low'] as Priority[]).map((p) => (
        <PriorityBadge key={p} priority={p} />
      ))}
    </div>
  ),
}
