import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { AgentGridView } from '@/pages/agents/AgentGridView'
import { makeAgent } from '../../helpers/factories'

function renderWithRouter(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('AgentGridView', () => {
  it('renders empty state when no agents', () => {
    renderWithRouter(<AgentGridView agents={[]} />)
    expect(screen.getByText('No agents found')).toBeInTheDocument()
    expect(screen.getByText('Try adjusting your filters or search query.')).toBeInTheDocument()
  })

  it('renders agent cards when agents provided', () => {
    const agents = [makeAgent('alice'), makeAgent('bob')]
    renderWithRouter(<AgentGridView agents={agents} />)
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByText('bob')).toBeInTheDocument()
  })

  it('links to correct agent detail URL with encoded name', () => {
    const agents = [makeAgent('alice doe')]
    renderWithRouter(<AgentGridView agents={agents} />)
    const link = screen.getByRole('link', { name: /alice doe/i })
    expect(link).toHaveAttribute('href', '/agents/alice%20doe')
  })
})
