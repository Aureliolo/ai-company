import { waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useProjectsStore } from '@/stores/projects'
import { makeProject, makeTask } from '../helpers/factories'
import { apiError, apiSuccess, paginatedFor } from '@/mocks/handlers'
import type { listProjects } from '@/api/endpoints/projects'
import type { listTasks } from '@/api/endpoints/tasks'
import { server } from '@/test-setup'
import type { Project } from '@/api/types/projects'
import type { Task } from '@/api/types/tasks'
import type { WsEvent } from '@/api/types/websocket'

function paginatedProjects(data: Project[], total?: number) {
  const resolvedTotal = total ?? data.length
  return paginatedFor<typeof listProjects>({
    data,
    total: resolvedTotal,
    offset: 0,
    limit: 200,
    nextCursor: null,
    hasMore: false,
    pagination: {
      total: resolvedTotal,
      offset: 0,
      limit: 200,
      next_cursor: null,
      has_more: false,
    },
  })
}

function paginatedTasks(data: Task[], total?: number) {
  const resolvedTotal = total ?? data.length
  return paginatedFor<typeof listTasks>({
    data,
    total: resolvedTotal,
    offset: 0,
    limit: 50,
    nextCursor: null,
    hasMore: false,
    pagination: {
      total: resolvedTotal,
      offset: 0,
      limit: 50,
      next_cursor: null,
      has_more: false,
    },
  })
}

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
  })

  describe('fetchProjects', () => {
    it('populates projects on success', async () => {
      const project = makeProject('proj-001')
      server.use(
        http.get('/api/v1/projects', () =>
          HttpResponse.json(paginatedProjects([project], 1)),
        ),
      )

      await useProjectsStore.getState().fetchProjects()

      const state = useProjectsStore.getState()
      expect(state.projects).toEqual([project])
      expect(state.totalProjects).toBe(1)
      expect(state.listLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      server.use(
        http.get('/api/v1/projects', () =>
          HttpResponse.json(apiError('Network error')),
        ),
      )

      await useProjectsStore.getState().fetchProjects()

      expect(useProjectsStore.getState().listError).toBe('Network error')
    })
  })

  describe('fetchProjectDetail', () => {
    it('populates selected project and tasks', async () => {
      const project = makeProject('proj-001')
      const task = makeTask('task-001')
      server.use(
        http.get('/api/v1/projects/:id', () =>
          HttpResponse.json(apiSuccess(project)),
        ),
        http.get('/api/v1/tasks', () =>
          HttpResponse.json(paginatedTasks([task], 1)),
        ),
      )

      await useProjectsStore.getState().fetchProjectDetail('proj-001')

      const state = useProjectsStore.getState()
      expect(state.selectedProject).toEqual(project)
      expect(state.projectTasks).toEqual([task])
    })

    it('sets error when project not found', async () => {
      server.use(
        http.get('/api/v1/projects/:id', () =>
          HttpResponse.json(apiError('Not found')),
        ),
        http.get('/api/v1/tasks', () =>
          HttpResponse.json(apiError('Not found')),
        ),
      )

      await useProjectsStore.getState().fetchProjectDetail('missing')

      expect(useProjectsStore.getState().detailError).toBe('Not found')
    })

    it('handles partial task failure gracefully', async () => {
      const project = makeProject('proj-001')
      server.use(
        http.get('/api/v1/projects/:id', () =>
          HttpResponse.json(apiSuccess(project)),
        ),
        http.get('/api/v1/tasks', () =>
          HttpResponse.json(apiError('task fetch failed')),
        ),
      )

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
      let capturedBody: unknown = null
      server.use(
        http.post('/api/v1/projects', async ({ request }) => {
          capturedBody = await request.json()
          return HttpResponse.json(apiSuccess(project))
        }),
      )

      const result = await useProjectsStore
        .getState()
        .createProject({ name: 'New Project' })

      expect(result).toEqual(project)
      expect(capturedBody).toEqual({ name: 'New Project' })

      const state = useProjectsStore.getState()
      expect(state.projects).toContainEqual(project)
      expect(state.totalProjects).toBe(1)
    })

    it('returns null sentinel + emits error toast on failure', async () => {
      const { useToastStore } = await import('@/stores/toast')
      useToastStore.getState().dismissAll()
      server.use(
        http.post('/api/v1/projects', () =>
          HttpResponse.json(apiError('Create failed'), { status: 400 }),
        ),
      )

      const result = await useProjectsStore
        .getState()
        .createProject({ name: 'Fail' })

      expect(result).toBeNull()
      expect(useProjectsStore.getState().projects).toEqual([])
      expect(useProjectsStore.getState().totalProjects).toBe(0)
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.variant).toBe('error')
      expect(toasts[0]!.title).toBe('Failed to create project')
    })
  })

  describe('updateFromWsEvent', () => {
    it('triggers fetchProjects on WS event', async () => {
      let fetchCount = 0
      server.use(
        http.get('/api/v1/projects', () => {
          fetchCount += 1
          return HttpResponse.json(paginatedProjects([]))
        }),
      )

      const event: WsEvent = {
        event_type: 'project.created',
        channel: 'projects',
        timestamp: '2026-03-31T12:00:00Z',
        payload: { project_id: 'proj-new', name: 'New' },
      }
      useProjectsStore.getState().updateFromWsEvent(event)

      await waitFor(() => {
        expect(fetchCount).toBeGreaterThan(0)
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
