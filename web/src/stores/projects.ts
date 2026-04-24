import { create } from 'zustand'
import {
  createProject as createProjectApi,
  deleteProject as deleteProjectApi,
  getProject,
  listProjects,
} from '@/api/endpoints/projects'
import { listTasks } from '@/api/endpoints/tasks'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import type { ProjectStatus } from '@/api/types/enums'
import type { CreateProjectRequest, Project } from '@/api/types/projects'
import type { Task } from '@/api/types/tasks'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('projects')

interface ProjectsState {
  // List page
  projects: readonly Project[]
  totalProjects: number
  listLoading: boolean
  listError: string | null

  // Filters
  searchQuery: string
  statusFilter: ProjectStatus | null
  leadFilter: string | null

  // Detail page
  selectedProject: Project | null
  projectTasks: readonly Task[]
  detailLoading: boolean
  detailError: string | null

  // Actions. Mutations follow the canonical store error contract:
  // log + error toast + return sentinel (`null`) on failure. Callers
  // MUST NOT wrap these in try/catch.
  fetchProjects: () => Promise<void>
  fetchProjectDetail: (id: string) => Promise<void>
  createProject: (data: CreateProjectRequest) => Promise<Project | null>
  deleteProject: (id: string) => Promise<boolean>
  batchDeleteProjects: (ids: readonly string[]) => Promise<{ succeeded: number; failed: number; failedReasons: string[] }>
  setSearchQuery: (q: string) => void
  setStatusFilter: (s: ProjectStatus | null) => void
  setLeadFilter: (l: string | null) => void
  clearDetail: () => void
  updateFromWsEvent: (event: WsEvent) => void
}

let _detailRequestToken = 0
/** True when a newer detail request has superseded this one. */
function isStaleDetailRequest(token: number): boolean { return _detailRequestToken !== token }

let _listRequestToken = 0
/** True when a newer list request has superseded this one. */
function isStaleListRequest(token: number): boolean { return _listRequestToken !== token }

export const useProjectsStore = create<ProjectsState>()((set) => ({
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

  fetchProjects: async () => {
    const token = ++_listRequestToken
    set({ listLoading: true, listError: null })
    try {
      const result = await listProjects({ limit: 200 })
      if (isStaleListRequest(token)) return
      set({ projects: result.data, totalProjects: result.total ?? result.data.length, listLoading: false })
    } catch (err) {
      if (isStaleListRequest(token)) return
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  fetchProjectDetail: async (id: string) => {
    const token = ++_detailRequestToken
    set({ detailLoading: true, detailError: null, selectedProject: null, projectTasks: [] })

    const [projectResult, tasksResult] = await Promise.allSettled([
      getProject(id),
      listTasks({ project: id, limit: 50 }),
    ])

    if (isStaleDetailRequest(token)) return

    const project = projectResult.status === 'fulfilled' ? projectResult.value : null
    if (!project) {
      const reason = projectResult.status === 'rejected' ? projectResult.reason : null
      set({ detailLoading: false, detailError: getErrorMessage(reason ?? 'Project not found'), selectedProject: null })
      return
    }

    const partialErrors: string[] = []
    if (tasksResult.status === 'rejected') partialErrors.push(`tasks: ${getErrorMessage(tasksResult.reason)}`)

    set({
      selectedProject: project,
      projectTasks: tasksResult.status === 'fulfilled' ? tasksResult.value.data : [],
      detailLoading: false,
      detailError: partialErrors.length > 0
        ? `Some data failed to load: ${partialErrors.join(', ')}. Displayed data may be incomplete.`
        : null,
    })
  },

  createProject: async (data: CreateProjectRequest) => {
    try {
      const project = await createProjectApi(data)
      // Optimistically add to local state for immediate UI update.
      // Filter by ID first to prevent duplicates if a concurrent fetch already added it.
      set((state) => {
        const exists = state.projects.some((p) => p.id === project.id)
        const filtered = state.projects.filter((p) => p.id !== project.id)
        return {
          projects: [project, ...filtered],
          totalProjects: exists ? state.totalProjects : state.totalProjects + 1,
        }
      })
      useToastStore.getState().add({
        variant: 'success',
        title: `Project ${project.name} created`,
      })
      // Polling and WS events will reconcile with server state.
      return project
    } catch (err) {
      log.error('Create project failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to create project',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  deleteProject: async (id: string) => {
    const previous = useProjectsStore.getState()
    set((state) => {
      const filtered = state.projects.filter((p) => p.id !== id)
      return {
        projects: filtered,
        totalProjects: state.projects.length !== filtered.length
          ? Math.max(0, state.totalProjects - 1)
          : state.totalProjects,
      }
    })
    try {
      await deleteProjectApi(id)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Project deleted',
      })
      return true
    } catch (err) {
      log.error('Delete project failed:', sanitizeForLog(err))
      set({ projects: previous.projects, totalProjects: previous.totalProjects })
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to delete project',
        description: getErrorMessage(err),
      })
      return false
    }
  },

  batchDeleteProjects: async (ids: readonly string[]) => {
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        await deleteProjectApi(id)
        return id
      }),
    )
    const succeededIds: string[] = []
    const failedReasons: string[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        succeededIds.push(result.value)
      } else {
        const id = ids[index] ?? '<unknown>'
        failedReasons.push(`${id}: ${getErrorMessage(result.reason)}`)
      }
    })
    if (succeededIds.length > 0) {
      const deletedSet = new Set(succeededIds)
      set((state) => {
        const filtered = state.projects.filter((p) => !deletedSet.has(p.id))
        return {
          projects: filtered,
          totalProjects: Math.max(0, state.totalProjects - succeededIds.length),
        }
      })
    }
    return {
      succeeded: succeededIds.length,
      failed: ids.length - succeededIds.length,
      failedReasons,
    }
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setStatusFilter: (s) => set({ statusFilter: s }),
  setLeadFilter: (l) => set({ leadFilter: l }),

  clearDetail: () => {
    ++_detailRequestToken
    set({
      selectedProject: null,
      projectTasks: [],
      detailLoading: false,
      detailError: null,
    })
  },

  // Event payload ignored -- all events trigger a full refetch.
  // Incremental updates are not worth the complexity given 30s polling.
  updateFromWsEvent: () => {
    useProjectsStore.getState().fetchProjects()
  },
}))
