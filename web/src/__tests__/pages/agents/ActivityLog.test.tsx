import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ActivityLog } from '@/pages/agents/ActivityLog'
import { makeActivityEvent } from '../../helpers/factories'

describe('ActivityLog', () => {
  it('renders empty state when no events', () => {
    render(<ActivityLog events={[]} total={0} onLoadMore={vi.fn()} />)
    expect(screen.getByText('No activity yet')).toBeInTheDocument()
    expect(screen.getByText('Recent actions will appear here.')).toBeInTheDocument()
  })

  it('renders events when provided', () => {
    const events = [
      makeActivityEvent({ description: 'Completed task A' }),
      makeActivityEvent({ description: 'Started task B' }),
    ]
    render(<ActivityLog events={events} total={2} onLoadMore={vi.fn()} />)
    expect(screen.getByText('Completed task A')).toBeInTheDocument()
    expect(screen.getByText('Started task B')).toBeInTheDocument()
  })

  it('shows load-more button when more events available', () => {
    const events = [makeActivityEvent()]
    render(<ActivityLog events={events} total={5} onLoadMore={vi.fn()} />)
    expect(screen.getByText('Load more')).toBeInTheDocument()
  })

  it('hides load-more button when all events loaded', () => {
    const events = [makeActivityEvent()]
    render(<ActivityLog events={events} total={1} onLoadMore={vi.fn()} />)
    expect(screen.queryByText('Load more')).not.toBeInTheDocument()
  })

  it('calls onLoadMore when button clicked', async () => {
    const onLoadMore = vi.fn()
    const user = userEvent.setup()
    render(<ActivityLog events={[makeActivityEvent()]} total={5} onLoadMore={onLoadMore} />)
    await user.click(screen.getByText('Load more'))
    expect(onLoadMore).toHaveBeenCalledOnce()
  })
})
