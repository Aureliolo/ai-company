import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChannelSidebar } from '@/pages/messages/ChannelSidebar'
import { makeChannel } from '../../helpers/factories'

describe('ChannelSidebar', () => {
  const defaultProps = {
    channels: [
      makeChannel('#engineering'),
      makeChannel('#product'),
      makeChannel('#dm-alice', { type: 'direct' as const }),
    ],
    activeChannel: null as string | null,
    unreadCounts: {} as Record<string, number>,
    onSelectChannel: vi.fn(),
    loading: false,
  }

  it('renders channel names', () => {
    render(<ChannelSidebar {...defaultProps} />)
    expect(screen.getByText('#engineering')).toBeInTheDocument()
    expect(screen.getByText('#product')).toBeInTheDocument()
    expect(screen.getByText('#dm-alice')).toBeInTheDocument()
  })

  it('groups channels by type', () => {
    render(<ChannelSidebar {...defaultProps} />)
    expect(screen.getByText('Topics')).toBeInTheDocument()
    expect(screen.getByText('Direct')).toBeInTheDocument()
  })

  it('highlights active channel', () => {
    render(<ChannelSidebar {...defaultProps} activeChannel="#engineering" />)
    const active = screen.getByText('#engineering').closest('button')
    expect(active).toHaveAttribute('aria-current', 'page')
  })

  it('shows unread badge count', () => {
    render(<ChannelSidebar {...defaultProps} unreadCounts={{ '#product': 5 }} />)
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('hides unread badge when count is zero', () => {
    render(<ChannelSidebar {...defaultProps} unreadCounts={{ '#product': 0 }} />)
    // Should not have a badge element for 0
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument()
  })

  it('calls onSelectChannel when clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<ChannelSidebar {...defaultProps} onSelectChannel={onSelect} />)

    await user.click(screen.getByText('#product'))
    expect(onSelect).toHaveBeenCalledWith('#product')
  })

  it('shows skeleton when loading with no channels', () => {
    render(<ChannelSidebar {...defaultProps} channels={[]} loading={true} />)
    expect(screen.getByLabelText('Channels')).toBeInTheDocument()
  })

  it('shows empty state when no channels', () => {
    render(<ChannelSidebar {...defaultProps} channels={[]} />)
    expect(screen.getByText('No channels')).toBeInTheDocument()
  })
})
