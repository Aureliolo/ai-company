import axios from 'axios'
import { create } from 'zustand'
import { useShallow } from 'zustand/react/shallow'

import {
  createTrainingPlan,
  executeTrainingPlan,
  getLatestTrainingPlan,
  getTrainingResult,
  previewTrainingPlan,
  updateTrainingOverrides,
  type TrainingOverridesRequest,
  type TrainingPlanRequest,
  type TrainingPlanResponse,
  type TrainingResultResponse,
} from '@/api/endpoints/training'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import { getErrorMessage } from '@/utils/errors'
import { useToastStore } from '@/stores/toast'

const log = createLogger('training')

type PerAgent<T> = Readonly<Record<string, T | null>>

type LoadingMap = Readonly<Record<string, boolean>>
type ErrorMap = Readonly<Record<string, string | null>>

interface TrainingState {
  plansByAgent: PerAgent<TrainingPlanResponse>
  resultsByAgent: PerAgent<TrainingResultResponse>
  loading: LoadingMap
  error: ErrorMap

  fetchPlan: (agentName: string) => Promise<void>
  fetchResult: (agentName: string) => Promise<void>
  hydrateForAgent: (agentName: string) => Promise<void>
  createPlan: (
    agentName: string,
    overrides: TrainingPlanRequest,
  ) => Promise<TrainingPlanResponse | null>
  executePlan: (agentName: string) => Promise<TrainingResultResponse | null>
  previewPlan: (agentName: string) => Promise<TrainingResultResponse | null>
  updateOverrides: (
    agentName: string,
    planId: string,
    data: TrainingOverridesRequest,
  ) => Promise<TrainingPlanResponse | null>
}

function setMap<V>(
  map: Readonly<Record<string, V>>,
  key: string,
  value: V,
): Readonly<Record<string, V>> {
  return { ...map, [key]: value }
}

/**
 * 404 is the expected signal that nothing has been persisted yet for
 * the agent; we clear the cache entry and suppress the toast/error.
 */
function isExpectedNotFound(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 404
}

export const useTrainingStore = create<TrainingState>()((set, get) => ({
  plansByAgent: {},
  resultsByAgent: {},
  loading: {},
  error: {},

  fetchPlan: async (agentName) => {
    try {
      const plan = await getLatestTrainingPlan(agentName)
      set((state) => ({
        plansByAgent: setMap(state.plansByAgent, agentName, plan),
        // A successful read clears any stale per-agent error banner.
        error: setMap(state.error, agentName, null),
      }))
    } catch (err) {
      if (isExpectedNotFound(err)) {
        set((state) => ({
          plansByAgent: setMap(state.plansByAgent, agentName, null),
          error: setMap(state.error, agentName, null),
        }))
        return
      }
      log.error(
        'fetchPlan failed',
        sanitizeForLog({ agentName, err, message: getErrorMessage(err) }),
      )
      set((state) => ({
        error: setMap(state.error, agentName, getErrorMessage(err)),
      }))
    }
  },

  fetchResult: async (agentName) => {
    set((state) => ({
      loading: setMap(state.loading, agentName, true),
      error: setMap(state.error, agentName, null),
    }))
    try {
      const result = await getTrainingResult(agentName)
      set((state) => ({
        resultsByAgent: setMap(state.resultsByAgent, agentName, result),
        loading: setMap(state.loading, agentName, false),
        // Successful read supersedes any older per-agent error banner
        // so overlapping requests cannot leave stale state behind.
        error: setMap(state.error, agentName, null),
      }))
    } catch (err) {
      if (isExpectedNotFound(err)) {
        set((state) => ({
          resultsByAgent: setMap(state.resultsByAgent, agentName, null),
          loading: setMap(state.loading, agentName, false),
          error: setMap(state.error, agentName, null),
        }))
        return
      }
      const message = getErrorMessage(err)
      log.error(
        'fetchResult failed',
        sanitizeForLog({ agentName, err, message }),
      )
      set((state) => ({
        loading: setMap(state.loading, agentName, false),
        error: setMap(state.error, agentName, message),
      }))
    }
  },

  hydrateForAgent: async (agentName) => {
    await Promise.all([get().fetchPlan(agentName), get().fetchResult(agentName)])
  },

  createPlan: async (agentName, overrides) => {
    try {
      const plan = await createTrainingPlan(agentName, overrides)
      set((state) => ({
        plansByAgent: setMap(state.plansByAgent, agentName, plan),
      }))
      useToastStore.getState().add({
        variant: 'success',
        title: 'Training plan created',
      })
      return plan
    } catch (err) {
      log.error(
        'createPlan failed',
        sanitizeForLog({ agentName, err, message: getErrorMessage(err) }),
      )
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to create training plan',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  executePlan: async (agentName) => {
    try {
      const result = await executeTrainingPlan(agentName)
      set((state) => {
        const next: Partial<TrainingState> = {
          resultsByAgent: setMap(state.resultsByAgent, agentName, result),
        }
        // Mirror the server-side plan transition to EXECUTED so the UI
        // (status badge, disabled "Execute" button) stays consistent
        // without a separate re-fetch.
        const cached = state.plansByAgent[agentName]
        if (cached) {
          next.plansByAgent = setMap(state.plansByAgent, agentName, {
            ...cached,
            status: 'executed',
            executed_at: result.completed_at,
          })
        }
        return next
      })
      useToastStore.getState().add({
        variant: 'success',
        title: 'Training executed',
      })
      return result
    } catch (err) {
      log.error(
        'executePlan failed',
        sanitizeForLog({ agentName, err, message: getErrorMessage(err) }),
      )
      useToastStore.getState().add({
        variant: 'error',
        title: 'Training execution failed',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  previewPlan: async (agentName) => {
    try {
      const preview = await previewTrainingPlan(agentName)
      return preview
    } catch (err) {
      log.error(
        'previewPlan failed',
        sanitizeForLog({ agentName, err, message: getErrorMessage(err) }),
      )
      useToastStore.getState().add({
        variant: 'error',
        title: 'Training preview failed',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  updateOverrides: async (agentName, planId, data) => {
    try {
      const plan = await updateTrainingOverrides(agentName, planId, data)
      set((state) => ({
        plansByAgent: setMap(state.plansByAgent, agentName, plan),
      }))
      useToastStore.getState().add({
        variant: 'success',
        title: 'Overrides saved',
      })
      return plan
    } catch (err) {
      log.error(
        'updateOverrides failed',
        sanitizeForLog({
          agentName,
          planId,
          err,
          message: getErrorMessage(err),
        }),
      )
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to save overrides',
        description: getErrorMessage(err),
      })
      return null
    }
  },
}))

export interface TrainingForAgent {
  plan: TrainingPlanResponse | null
  result: TrainingResultResponse | null
  loading: boolean
  error: string | null
}

/**
 * Subscribe to the training state for a single agent. Uses
 * ``useShallow`` so re-renders only fire when one of the underlying
 * fields changes, not on every store update.
 */
export function useTrainingForAgent(agentName: string): TrainingForAgent {
  return useTrainingStore(
    useShallow((state): TrainingForAgent => ({
      plan: state.plansByAgent[agentName] ?? null,
      result: state.resultsByAgent[agentName] ?? null,
      loading: state.loading[agentName] ?? false,
      error: state.error[agentName] ?? null,
    })),
  )
}
