import { render, screen } from '@testing-library/react'
import type { Priority, TaskStatus } from '@/api/types'
import { TaskStatusIndicator, PriorityBadge } from '@/components/ui/task-status-indicator'

const ALL_STATUSES: TaskStatus[] = [
  'created', 'assigned', 'in_progress', 'in_review', 'completed',
  'blocked', 'failed', 'interrupted', 'cancelled',
]

const STATUS_LABELS: Record<TaskStatus, string> = {
  created: 'Created',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  in_review: 'In Review',
  completed: 'Completed',
  blocked: 'Blocked',
  failed: 'Failed',
  interrupted: 'Interrupted',
  cancelled: 'Cancelled',
}

describe('TaskStatusIndicator', () => {
  it.each(ALL_STATUSES)('renders dot for status %s', (status) => {
    render(<TaskStatusIndicator status={status} />)
    expect(screen.getByLabelText(STATUS_LABELS[status])).toBeInTheDocument()
  })

  it('renders label text when label prop is true', () => {
    render(<TaskStatusIndicator status="in_progress" label />)
    expect(screen.getByText('In Progress')).toBeInTheDocument()
  })

  it('does not render label text by default', () => {
    render(<TaskStatusIndicator status="in_progress" />)
    expect(screen.queryByText('In Progress')).not.toBeInTheDocument()
  })

  it('applies pulse animation class when pulse prop is true', () => {
    render(<TaskStatusIndicator status="blocked" pulse />)
    const dot = screen.getByLabelText('Blocked').querySelector('[data-slot="status-dot"]')
    expect(dot).toHaveClass('animate-pulse')
  })

  it('applies custom className', () => {
    render(<TaskStatusIndicator status="assigned" className="ml-2" />)
    expect(screen.getByLabelText('Assigned')).toHaveClass('ml-2')
  })
})

describe('PriorityBadge', () => {
  const priorities: Priority[] = ['critical', 'high', 'medium', 'low']
  const labels: Record<Priority, string> = {
    critical: 'Critical',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  }

  it.each(priorities)('renders label for priority %s', (priority) => {
    render(<PriorityBadge priority={priority} />)
    expect(screen.getByText(labels[priority])).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<PriorityBadge priority="high" className="ml-4" />)
    expect(container.firstChild).toHaveClass('ml-4')
  })
})
