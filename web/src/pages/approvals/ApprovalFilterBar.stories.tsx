import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { ApprovalFilterBar } from './ApprovalFilterBar'
import type { ApprovalPageFilters } from '@/utils/approvals'

const meta: Meta<typeof ApprovalFilterBar> = {
  title: 'Pages/Approvals/ApprovalFilterBar',
  component: ApprovalFilterBar,
  parameters: {
    a11y: { test: 'error' },
  },
}
export default meta

type Story = StoryObj<typeof ApprovalFilterBar>

function Interactive() {
  const [filters, setFilters] = useState<ApprovalPageFilters>({})
  return (
    <ApprovalFilterBar
      filters={filters}
      onFiltersChange={setFilters}
      pendingCount={12}
      totalCount={45}
      actionTypes={['code:create', 'deploy:production', 'vcs:push', 'db:mutate', 'org:hire']}
    />
  )
}

export const Default: Story = {
  render: () => <Interactive />,
}

export const WithActiveFilters: Story = {
  args: {
    filters: { status: 'pending', riskLevel: 'critical' },
    onFiltersChange: () => {},
    pendingCount: 3,
    totalCount: 45,
    actionTypes: ['code:create', 'deploy:production'],
  },
}

export const Empty: Story = {
  args: {
    filters: {},
    onFiltersChange: () => {},
    pendingCount: 0,
    totalCount: 0,
    actionTypes: [],
  },
}
