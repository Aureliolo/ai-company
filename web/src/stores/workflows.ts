import { create } from 'zustand'
import {
  listWorkflows,
  listBlueprints,
  createWorkflow as createWorkflowApi,
  createFromBlueprint as createFromBlueprintApi,
  deleteWorkflow as deleteWorkflowApi,
} from '@/api/endpoints/workflows'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type {
  BlueprintInfo,
  CreateFromBlueprintRequest,
  CreateWorkflowDefinitionRequest,
  WorkflowDefinition,
} from '@/api/types'

const log = createLogger('workflows')

interface WorkflowsState {
  // List
  workflows: readonly WorkflowDefinition[]
  totalWorkflows: number
  listLoading: boolean
  listError: string | null

  // Blueprints
  blueprints: readonly BlueprintInfo[]
  blueprintsLoading: boolean
  blueprintsError: string | null

  // Filters
  searchQuery: string
  workflowTypeFilter: string | null

  // Actions
  fetchWorkflows: () => Promise<void>
  loadBlueprints: () => Promise<void>
  createWorkflow: (data: CreateWorkflowDefinitionRequest) => Promise<WorkflowDefinition>
  createFromBlueprint: (data: CreateFromBlueprintRequest) => Promise<WorkflowDefinition>
  deleteWorkflow: (id: string) => Promise<void>
  setSearchQuery: (q: string) => void
  setWorkflowTypeFilter: (t: string | null) => void
  updateFromWsEvent: () => void
}

let _listRequestToken = 0
function isStaleListRequest(token: number): boolean {
  return _listRequestToken !== token
}

let _blueprintRequestToken = 0
function isStaleBlueprintRequest(token: number): boolean {
  return _blueprintRequestToken !== token
}

/** Upsert a workflow into the store list (prepends, deduplicates). */
function upsertWorkflow(
  set: (fn: (state: WorkflowsState) => Partial<WorkflowsState>) => void,
  workflow: WorkflowDefinition,
): void {
  set((state) => {
    const exists = state.workflows.some((w) => w.id === workflow.id)
    const filtered = state.workflows.filter((w) => w.id !== workflow.id)
    return {
      workflows: [workflow, ...filtered],
      totalWorkflows: exists ? state.totalWorkflows : state.totalWorkflows + 1,
    }
  })
}

export const useWorkflowsStore = create<WorkflowsState>()((set) => ({
  workflows: [],
  totalWorkflows: 0,
  listLoading: false,
  listError: null,

  blueprints: [],
  blueprintsLoading: false,
  blueprintsError: null,

  searchQuery: '',
  workflowTypeFilter: null,

  loadBlueprints: async () => {
    const token = ++_blueprintRequestToken
    set({ blueprintsLoading: true, blueprintsError: null })
    try {
      const data = await listBlueprints()
      if (isStaleBlueprintRequest(token)) return
      set({ blueprints: data, blueprintsLoading: false })
    } catch (err) {
      if (isStaleBlueprintRequest(token)) return
      log.warn('Failed to load blueprints', sanitizeForLog(err))
      set({ blueprintsLoading: false, blueprintsError: getErrorMessage(err) })
    }
  },

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
      log.warn('Failed to fetch workflows', sanitizeForLog(err))
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  createWorkflow: async (data: CreateWorkflowDefinitionRequest) => {
    const workflow = await createWorkflowApi(data)
    upsertWorkflow(set, workflow)
    return workflow
  },

  createFromBlueprint: async (data: CreateFromBlueprintRequest) => {
    const workflow = await createFromBlueprintApi(data)
    upsertWorkflow(set, workflow)
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
