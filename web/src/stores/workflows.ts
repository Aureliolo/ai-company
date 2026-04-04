import { create } from 'zustand'
import {
  listWorkflows,
  createWorkflow as createWorkflowApi,
  deleteWorkflow as deleteWorkflowApi,
} from '@/api/endpoints/workflows'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('workflows')
import type { CreateWorkflowDefinitionRequest, WorkflowDefinition } from '@/api/types'

interface WorkflowsState {
  // List
  workflows: readonly WorkflowDefinition[]
  totalWorkflows: number
  listLoading: boolean
  listError: string | null

  // Filters
  searchQuery: string
  workflowTypeFilter: string | null

  // Actions
  fetchWorkflows: () => Promise<void>
  createWorkflow: (data: CreateWorkflowDefinitionRequest) => Promise<WorkflowDefinition>
  deleteWorkflow: (id: string) => Promise<void>
  setSearchQuery: (q: string) => void
  setWorkflowTypeFilter: (t: string | null) => void
  updateFromWsEvent: () => void
}

let _listRequestToken = 0
function isStaleListRequest(token: number): boolean {
  return _listRequestToken !== token
}

export const useWorkflowsStore = create<WorkflowsState>()((set) => ({
  workflows: [],
  totalWorkflows: 0,
  listLoading: false,
  listError: null,

  searchQuery: '',
  workflowTypeFilter: null,

  fetchWorkflows: async () => {
    const token = ++_listRequestToken
    set({ listLoading: true, listError: null })
    try {
      const result = await listWorkflows({ limit: 200 })
      if (isStaleListRequest(token)) return
      set({
        workflows: result.data,
        totalWorkflows: result.total,
        listLoading: false,
      })
    } catch (err) {
      if (isStaleListRequest(token)) return
      log.warn('Failed to fetch workflows', err)
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  createWorkflow: async (data: CreateWorkflowDefinitionRequest) => {
    const workflow = await createWorkflowApi(data)
    set((state) => {
      const exists = state.workflows.some((w) => w.id === workflow.id)
      const filtered = state.workflows.filter((w) => w.id !== workflow.id)
      return {
        workflows: [workflow, ...filtered],
        totalWorkflows: exists ? state.totalWorkflows : state.totalWorkflows + 1,
      }
    })
    return workflow
  },

  deleteWorkflow: async (id: string) => {
    await deleteWorkflowApi(id)
    set((state) => {
      const filtered = state.workflows.filter((w) => w.id !== id)
      return {
        workflows: filtered,
        totalWorkflows: filtered.length < state.workflows.length
          ? Math.max(0, state.totalWorkflows - 1)
          : state.totalWorkflows,
      }
    })
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setWorkflowTypeFilter: (t) => set({ workflowTypeFilter: t }),

  updateFromWsEvent: () => {
    useWorkflowsStore.getState().fetchWorkflows()
  },
}))
