import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseArtifactsDataReturn } from '@/hooks/useArtifactsData'
import { makeArtifact } from '../helpers/factories'

/* eslint-disable @eslint-react/component-hook-factories -- vi.mock factories define stub components for module replacement */
vi.mock('@/pages/artifacts/ArtifactsSkeleton', () => ({
  ArtifactsSkeleton: () => <div data-testid="artifacts-skeleton" />,
}))
vi.mock('@/pages/artifacts/ArtifactFilters', () => ({
  ArtifactFilters: () => <div data-testid="artifact-filters" />,
}))
vi.mock('@/pages/artifacts/ArtifactGridView', () => ({
  ArtifactGridView: () => <div data-testid="artifact-grid-view" />,
}))
/* eslint-enable @eslint-react/component-hook-factories */

const defaultHookReturn: UseArtifactsDataReturn = {
  artifacts: [makeArtifact('artifact-001')],
  filteredArtifacts: [makeArtifact('artifact-001')],
  totalArtifacts: 1,
  loading: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
}

let hookReturn = { ...defaultHookReturn }

const getArtifactsData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useArtifactsData', () => {
  const hookName = 'useArtifactsData'
  return { [hookName]: () => getArtifactsData() }
})

import ArtifactsPage from '@/pages/ArtifactsPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <ArtifactsPage />
    </MemoryRouter>,
  )
}

describe('ArtifactsPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('Artifacts')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultHookReturn, loading: true, totalArtifacts: 0, artifacts: [], filteredArtifacts: [] }
    renderPage()
    expect(screen.getByTestId('artifacts-skeleton')).toBeInTheDocument()
  })

  it('renders artifact count', () => {
    renderPage()
    expect(screen.getByText('1 of 1')).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    renderPage()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data already exists', () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    renderPage()
    expect(screen.getByText('Artifacts')).toBeInTheDocument()
    expect(screen.queryByTestId('artifacts-skeleton')).not.toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning when not connected', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    renderPage()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })
})
