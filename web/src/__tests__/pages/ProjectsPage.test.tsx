import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseProjectsDataReturn } from '@/hooks/useProjectsData'
import { makeProject } from '../helpers/factories'


vi.mock('@/pages/projects/ProjectsSkeleton', () => ({
  ProjectsSkeleton: () => <div data-testid="projects-skeleton" />,
}))
vi.mock('@/pages/projects/ProjectFilters', () => ({
  ProjectFilters: () => <div data-testid="project-filters" />,
}))
vi.mock('@/pages/projects/ProjectGridView', () => ({
  ProjectGridView: () => <div data-testid="project-grid-view" />,
}))
vi.mock('@/pages/projects/ProjectCreateDrawer', () => ({
  ProjectCreateDrawer: () => <div data-testid="project-create-drawer" />,
}))


const defaultHookReturn: UseProjectsDataReturn = {
  projects: [makeProject('proj-001')],
  filteredProjects: [makeProject('proj-001')],
  totalProjects: 1,
  loading: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
}

let hookReturn = { ...defaultHookReturn }

const getProjectsData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useProjectsData', () => {
  const hookName = 'useProjectsData'
  return { [hookName]: () => getProjectsData() }
})

import ProjectsPage from '@/pages/ProjectsPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  )
}

describe('ProjectsPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultHookReturn, loading: true, totalProjects: 0, projects: [], filteredProjects: [] }
    renderPage()
    expect(screen.getByTestId('projects-skeleton')).toBeInTheDocument()
  })

  it('renders project count', () => {
    renderPage()
    expect(screen.getByText('1 of 1')).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    renderPage()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('renders create project button', () => {
    renderPage()
    expect(screen.getByText('Create Project')).toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning when not connected', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    renderPage()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })
})
