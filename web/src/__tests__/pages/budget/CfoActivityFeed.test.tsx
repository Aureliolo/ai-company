import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import * as fc from 'fast-check'
import { CfoActivityFeed } from '@/pages/budget/CfoActivityFeed'
import type { ActivityItem } from '@/api/types/analytics'

function makeEvents(count: number): ActivityItem[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `event-${i}`,
    timestamp: new Date(Date.now() - i * 60_000).toISOString(),
    agent_name: `agent-${i}`,
    action_type: 'budget.record_added' as const,
    description: `Recorded a cost ${i}`,
    task_id: null,
    department: null,
  }))
}

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('CfoActivityFeed', () => {
  it('renders section title', () => {
    renderWithRouter(<CfoActivityFeed events={[]} />)
    expect(screen.getByText('CFO Optimization Events')).toBeInTheDocument()
  })

  it('shows empty state when no events', () => {
    renderWithRouter(<CfoActivityFeed events={[]} />)
    expect(screen.getByText('No budget events')).toBeInTheDocument()
    expect(
      screen.getByText('Budget decisions and alerts will appear here'),
    ).toBeInTheDocument()
  })

  it('renders event items', () => {
    renderWithRouter(<CfoActivityFeed events={makeEvents(3)} />)
    expect(screen.getByText('agent-0')).toBeInTheDocument()
    expect(screen.getByText('agent-1')).toBeInTheDocument()
    expect(screen.getByText('agent-2')).toBeInTheDocument()
  })

  it('caps displayed items at 10', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 30 }), (count) => {
        const { unmount } = renderWithRouter(
          <CfoActivityFeed events={makeEvents(count)} />,
        )
        const visible = Math.min(count, 10)
        for (let i = 0; i < visible; i++) {
          expect(screen.getByText(`agent-${i}`)).toBeInTheDocument()
        }
        if (count > 10) {
          expect(screen.queryByText('agent-10')).not.toBeInTheDocument()
        }
        unmount()
      }),
      { numRuns: 10 },
    )
  })

  it('renders descriptions for each event', () => {
    renderWithRouter(<CfoActivityFeed events={makeEvents(2)} />)
    expect(screen.getByText('Recorded a cost 0')).toBeInTheDocument()
    expect(screen.getByText('Recorded a cost 1')).toBeInTheDocument()
  })

  it('renders log region when events are present', () => {
    renderWithRouter(<CfoActivityFeed events={makeEvents(1)} />)
    expect(screen.getByRole('log')).toBeInTheDocument()
  })

  it('does not render log region when empty', () => {
    renderWithRouter(<CfoActivityFeed events={[]} />)
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })
})
