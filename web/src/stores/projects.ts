import { create } from 'zustand'
import { listProjects, getProject, createProject as createProjectApi } from '@/api/endpoints/projects'
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
