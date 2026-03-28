import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MessageFilterBar } from '@/pages/messages/MessageFilterBar'

describe('MessageFilterBar', () => {
  const defaultProps = {
    filters: {},
    onFiltersChange: vi.fn(),
    totalCount: 42,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders type and priority selects and search input', () => {
    render(<MessageFilterBar {...defaultProps} />)
    expect(screen.getByLabelText('Filter by message type')).toBeInTheDocument()
    expect(screen.getByLabelText('Filter by priority')).toBeInTheDocument()
    expect(screen.getByLabelText('Search messages')).toBeInTheDocument()
  })

  it('shows total message count when no filters', () => {
    render(<MessageFilterBar {...defaultProps} />)
    expect(screen.getByText('42 messages')).toBeInTheDocument()
  })

  it('shows filtered count when filters active', () => {
    render(<MessageFilterBar {...defaultProps} filters={{ type: 'delegation' }} filteredCount={8} />)
    expect(screen.getByText('8 of 42')).toBeInTheDocument()
  })

  it('calls onFiltersChange when type select changes', async () => {
    const user = userEvent.setup()
    const onFiltersChange = vi.fn()
    render(<MessageFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />)

    await user.selectOptions(screen.getByLabelText('Filter by message type'), 'delegation')
    expect(onFiltersChange).toHaveBeenCalledWith({ type: 'delegation' })
  })

  it('calls onFiltersChange when priority select changes', async () => {
    const user = userEvent.setup()
    const onFiltersChange = vi.fn()
    render(<MessageFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />)

    await user.selectOptions(screen.getByLabelText('Filter by priority'), 'high')
    expect(onFiltersChange).toHaveBeenCalledWith({ priority: 'high' })
  })

  it('calls onFiltersChange when search input changes', async () => {
    const user = userEvent.setup()
    const onFiltersChange = vi.fn()
    render(<MessageFilterBar {...defaultProps} onFiltersChange={onFiltersChange} />)

    await user.type(screen.getByLabelText('Search messages'), 'h')
    expect(onFiltersChange).toHaveBeenCalledWith({ search: 'h' })
  })

  it('renders filter pills for active filters', () => {
    render(<MessageFilterBar {...defaultProps} filters={{ type: 'delegation', priority: 'high' }} />)
    // Filter pills have remove buttons with accessible labels
    expect(screen.getByLabelText('Remove Delegation filter')).toBeInTheDocument()
    expect(screen.getByLabelText('Remove High filter')).toBeInTheDocument()
  })

  it('renders search filter pill with quoted text', () => {
    render(<MessageFilterBar {...defaultProps} filters={{ search: 'hello' }} />)
    expect(screen.getByText('"hello"')).toBeInTheDocument()
  })

  it('removes filter when pill X is clicked', async () => {
    const user = userEvent.setup()
    const onFiltersChange = vi.fn()
    render(<MessageFilterBar {...defaultProps} filters={{ type: 'delegation' }} onFiltersChange={onFiltersChange} />)

    await user.click(screen.getByLabelText('Remove Delegation filter'))
    expect(onFiltersChange).toHaveBeenCalledWith({ type: undefined })
  })

  it('clears all filters when Clear all is clicked', async () => {
    const user = userEvent.setup()
    const onFiltersChange = vi.fn()
    render(<MessageFilterBar {...defaultProps} filters={{ type: 'delegation', priority: 'high' }} onFiltersChange={onFiltersChange} />)

    await user.click(screen.getByText('Clear all'))
    expect(onFiltersChange).toHaveBeenCalledWith({})
  })

  it('does not show filter pills when no filters active', () => {
    render(<MessageFilterBar {...defaultProps} />)
    expect(screen.queryByText('Clear all')).not.toBeInTheDocument()
  })
})
