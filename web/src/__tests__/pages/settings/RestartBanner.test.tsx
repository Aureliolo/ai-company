import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RestartBanner } from '@/pages/settings/RestartBanner'

describe('RestartBanner', () => {
  it('renders nothing when count is 0', () => {
    const { container } = render(<RestartBanner count={0} onDismiss={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders banner with singular message when count is 1', () => {
    render(<RestartBanner count={1} onDismiss={() => {}} />)
    expect(screen.getByText(/1 setting requires a restart/i)).toBeInTheDocument()
  })

  it('renders banner with plural message when count > 1', () => {
    render(<RestartBanner count={3} onDismiss={() => {}} />)
    expect(screen.getByText(/3 settings require a restart/i)).toBeInTheDocument()
  })

  it('calls onDismiss when dismiss button is clicked', async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<RestartBanner count={2} onDismiss={onDismiss} />)
    await user.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('has warning role for accessibility', () => {
    render(<RestartBanner count={1} onDismiss={() => {}} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
