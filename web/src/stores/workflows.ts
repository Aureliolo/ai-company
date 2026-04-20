import { create } from 'zustand'
import {
  listWorkflows,
  listBlueprints,
  createWorkflow as createWorkflowApi,
  createFromBlueprint as createFromBlueprintApi,
  deleteWorkflow as deleteWorkflowApi,
} from '@/api/endpoints/workflows'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type {
  BlueprintInfo,
  CreateFromBlueprintRequest,
  CreateWorkflowDefinitionRequest,
  WorkflowDefinition,
} from '@/api/types/workflows'

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
  createWorkflow: (data: CreateWorkflowDefinitionRequest) => Promise<WorkflowDefinition | null>
  createFromBlueprint: (data: CreateFromBlueprintRequest) => Promise<WorkflowDefinition | null>
  deleteWorkflow: (id: string) => Promise<boolean>
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
    try {
      const workflow = await createWorkflowApi(data)
      upsertWorkflow(set, workflow)
      useToastStore.getState().add({
        variant: 'success',
        title: `Workflow ${workflow.name} created`,
      })
      return workflow
    } catch (err) {
      log.error('Create workflow failed', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to create workflow',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  createFromBlueprint: async (data: CreateFromBlueprintRequest) => {
    try {
      const workflow = await createFromBlueprintApi(data)
      upsertWorkflow(set, workflow)
      useToastStore.getState().add({
        variant: 'success',
        title: `Workflow ${workflow.name} created from blueprint`,
      })
      return workflow
    } catch (err) {
      log.error('Create workflow from blueprint failed', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to create workflow from blueprint',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  deleteWorkflow: async (id: string) => {
    const removed = useWorkflowsStore.getState().workflows.find((w) => w.id === id)
    set((state) => {
      const filtered = state.workflows.filter((w) => w.id !== id)
      return {
        workflows: filtered,
        totalWorkflows: filtered.length < state.workflows.length
          ? Math.max(0, state.totalWorkflows - 1)
          : state.totalWorkflows,
      }
    })
    try {
      await deleteWorkflowApi(id)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Workflow deleted',
      })
      return true
    } catch (err) {
      log.error('Delete workflow failed', sanitizeForLog(err))
      // Surgical rollback: re-insert just the removed workflow if it's still
      // missing.  Avoids clobbering concurrent WS-triggered state updates.
      if (removed) {
        set((state) => {
          if (state.workflows.some((w) => w.id === id)) return state
          return {
            workflows: [removed, ...state.workflows],
            totalWorkflows: state.totalWorkflows + 1,
          }
        })
      }
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to delete workflow',
        description: getErrorMessage(err),
      })
      return false
    }
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setWorkflowTypeFilter: (t) => set({ workflowTypeFilter: t }),

  updateFromWsEvent: () => {
    useWorkflowsStore.getState().fetchWorkflows()
  },
}))
