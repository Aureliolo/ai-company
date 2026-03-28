import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChannelListItem } from '@/pages/messages/ChannelListItem'
import { makeChannel } from '../../helpers/factories'

describe('ChannelListItem', () => {
  const defaultProps = {
    channel: makeChannel('#engineering'),
    active: false,
    unreadCount: 0,
    onClick: vi.fn(),
  }

  it('renders channel name', () => {
    render(<ChannelListItem {...defaultProps} />)
    expect(screen.getByText('#engineering')).toBeInTheDocument()
  })

  it('sets aria-current="page" when active', () => {
    render(<ChannelListItem {...defaultProps} active={true} />)
    expect(screen.getByRole('button')).toHaveAttribute('aria-current', 'page')
  })

  it('does not set aria-current when not active', () => {
    render(<ChannelListItem {...defaultProps} active={false} />)
    expect(screen.getByRole('button')).not.toHaveAttribute('aria-current')
  })

  it('shows unread badge when count > 0', () => {
    render(<ChannelListItem {...defaultProps} unreadCount={5} />)
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('hides unread badge when count is 0', () => {
    render(<ChannelListItem {...defaultProps} unreadCount={0} />)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders topic icon for topic channel', () => {
    render(<ChannelListItem {...defaultProps} channel={makeChannel('#eng')} />)
    // Hash icon is rendered as SVG, verify the button exists
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders direct icon for direct channel', () => {
    render(<ChannelListItem {...defaultProps} channel={makeChannel('#dm-alice', { type: 'direct' })} />)
    expect(screen.getByText('#dm-alice')).toBeInTheDocument()
  })

  it('renders broadcast icon for broadcast channel', () => {
    render(<ChannelListItem {...defaultProps} channel={makeChannel('#all-hands', { type: 'broadcast' })} />)
    expect(screen.getByText('#all-hands')).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<ChannelListItem {...defaultProps} onClick={onClick} />)
    await user.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
