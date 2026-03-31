import { waitFor } from '@testing-library/react'
import { useProjectsStore } from '@/stores/projects'
import { makeProject, makeTask } from '../helpers/factories'
import type { WsEvent } from '@/api/types'

vi.mock('@/api/endpoints/projects', () => ({
  listProjects: vi.fn(),
  getProject: vi.fn(),
  createProject: vi.fn(),
}))

vi.mock('@/api/endpoints/tasks', () => ({
  listTasks: vi.fn(),
}))

const { listProjects, getProject, createProject } =
  await import('@/api/endpoints/projects')
const { listTasks } = await import('@/api/endpoints/tasks')

describe('useProjectsStore', () => {
  beforeEach(() => {
    useProjectsStore.setState({
      projects: [],
      totalProjects: 0,
      listLoading: false,
      listError: null,
      searchQuery: '',
      statusFilter: null,
      leadFilter: null,
      selectedProject: null,
      projectTasks: [],
      detailLoading: false,
      detailError: null,
    })
    vi.clearAllMocks()
  })

  describe('fetchProjects', () => {
    it('populates projects on success', async () => {
      const project = makeProject('proj-001')
      vi.mocked(listProjects).mockResolvedValue({ data: [project], total: 1, offset: 0, limit: 200 })

      await useProjectsStore.getState().fetchProjects()

      const state = useProjectsStore.getState()
      expect(state.projects).toEqual([project])
      expect(state.totalProjects).toBe(1)
      expect(state.listLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(listProjects).mockRejectedValue(new Error('Network error'))

      await useProjectsStore.getState().fetchProjects()

      expect(useProjectsStore.getState().listError).toBe('Network error')
    })
  })

  describe('fetchProjectDetail', () => {
    it('populates selected project and tasks', async () => {
      const project = makeProject('proj-001')
      const task = makeTask('task-001')
      vi.mocked(getProject).mockResolvedValue(project)
      vi.mocked(listTasks).mockResolvedValue({ data: [task], total: 1, offset: 0, limit: 50 })

      await useProjectsStore.getState().fetchProjectDetail('proj-001')

      const state = useProjectsStore.getState()
      expect(state.selectedProject).toEqual(project)
      expect(state.projectTasks).toEqual([task])
    })

    it('sets error when project not found', async () => {
      vi.mocked(getProject).mockRejectedValue(new Error('Not found'))
      vi.mocked(listTasks).mockRejectedValue(new Error('Not found'))

      await useProjectsStore.getState().fetchProjectDetail('missing')

      expect(useProjectsStore.getState().detailError).toBe('Not found')
    })

    it('handles partial task failure gracefully', async () => {
      const project = makeProject('proj-001')
      vi.mocked(getProject).mockResolvedValue(project)
      vi.mocked(listTasks).mockRejectedValue(new Error('task fetch failed'))

      await useProjectsStore.getState().fetchProjectDetail('proj-001')

      const state = useProjectsStore.getState()
      expect(state.selectedProject).toEqual(project)
      expect(state.projectTasks).toEqual([])
      expect(state.detailError).toMatch(/tasks/)
    })
  })

  describe('createProject', () => {
    it('calls API and optimistically adds to state', async () => {
      const project = makeProject('proj-new')
      vi.mocked(createProject).mockResolvedValue(project)

      const result = await useProjectsStore.getState().createProject({ name: 'New Project' })

      expect(result).toEqual(project)
      expect(createProject).toHaveBeenCalledWith({ name: 'New Project' })

      const state = useProjectsStore.getState()
      expect(state.projects).toContainEqual(project)
      expect(state.totalProjects).toBe(1)
    })

    it('propagates error without modifying state', async () => {
      vi.mocked(createProject).mockRejectedValue(new Error('Create failed'))

      await expect(useProjectsStore.getState().createProject({ name: 'Fail' })).rejects.toThrow('Create failed')

      expect(useProjectsStore.getState().projects).toEqual([])
      expect(useProjectsStore.getState().totalProjects).toBe(0)
    })
  })

  describe('updateFromWsEvent', () => {
    it('triggers fetchProjects on WS event', async () => {
      vi.mocked(listProjects).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })

      const event: WsEvent = {
        event_type: 'project.created',
        channel: 'projects',
        timestamp: '2026-03-31T12:00:00Z',
        payload: { project_id: 'proj-new', name: 'New' },
      }
      useProjectsStore.getState().updateFromWsEvent(event)

      await waitFor(() => {
        expect(listProjects).toHaveBeenCalled()
      })
    })
  })

  describe('filters', () => {
    it('sets search query', () => {
      useProjectsStore.getState().setSearchQuery('test')
      expect(useProjectsStore.getState().searchQuery).toBe('test')
    })

    it('sets status filter', () => {
      useProjectsStore.getState().setStatusFilter('active')
      expect(useProjectsStore.getState().statusFilter).toBe('active')
    })
  })

  describe('clearDetail', () => {
    it('clears detail state', () => {
      useProjectsStore.setState({
        selectedProject: makeProject('proj-001'),
        projectTasks: [makeTask('task-001')],
        detailError: 'old error',
      })

      useProjectsStore.getState().clearDetail()

      const state = useProjectsStore.getState()
      expect(state.selectedProject).toBeNull()
      expect(state.projectTasks).toEqual([])
      expect(state.detailError).toBeNull()
    })
  })
})
