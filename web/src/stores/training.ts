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

/**
 * Plan and result fetches run in parallel (see ``hydrateForAgent``)
 * so they each need their own loading/error slot; sharing the same
 * keys races -- whichever request finishes last stomps the other's
 * state. The UI reads a merged view via ``useTrainingForAgent``.
 */
interface TrainingState {
  plansByAgent: PerAgent<TrainingPlanResponse>
  resultsByAgent: PerAgent<TrainingResultResponse>
  planLoading: LoadingMap
  resultLoading: LoadingMap
  planError: ErrorMap
  resultError: ErrorMap

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
  planLoading: {},
  resultLoading: {},
  planError: {},
  resultError: {},

  fetchPlan: async (agentName) => {
    set((state) => ({
      planLoading: setMap(state.planLoading, agentName, true),
      planError: setMap(state.planError, agentName, null),
    }))
    try {
      const plan = await getLatestTrainingPlan(agentName)
      set((state) => ({
        plansByAgent: setMap(state.plansByAgent, agentName, plan),
        planLoading: setMap(state.planLoading, agentName, false),
        planError: setMap(state.planError, agentName, null),
      }))
    } catch (err) {
      if (isExpectedNotFound(err)) {
        set((state) => ({
          plansByAgent: setMap(state.plansByAgent, agentName, null),
          planLoading: setMap(state.planLoading, agentName, false),
          planError: setMap(state.planError, agentName, null),
        }))
        return
      }
      log.error(
        'fetchPlan failed',
        sanitizeForLog({ agentName, err, message: getErrorMessage(err) }),
      )
      set((state) => ({
        planLoading: setMap(state.planLoading, agentName, false),
        planError: setMap(state.planError, agentName, getErrorMessage(err)),
      }))
    }
  },

  fetchResult: async (agentName) => {
    set((state) => ({
      resultLoading: setMap(state.resultLoading, agentName, true),
      resultError: setMap(state.resultError, agentName, null),
    }))
    try {
      const result = await getTrainingResult(agentName)
      set((state) => ({
        resultsByAgent: setMap(state.resultsByAgent, agentName, result),
        resultLoading: setMap(state.resultLoading, agentName, false),
        resultError: setMap(state.resultError, agentName, null),
      }))
    } catch (err) {
      if (isExpectedNotFound(err)) {
        set((state) => ({
          resultsByAgent: setMap(state.resultsByAgent, agentName, null),
          resultLoading: setMap(state.resultLoading, agentName, false),
          resultError: setMap(state.resultError, agentName, null),
        }))
        return
      }
      const message = getErrorMessage(err)
      log.error(
        'fetchResult failed',
        sanitizeForLog({ agentName, err, message }),
      )
      set((state) => ({
        resultLoading: setMap(state.resultLoading, agentName, false),
        resultError: setMap(state.resultError, agentName, message),
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
        // Fresh write supersedes any stale plan-read error banner.
        planError: setMap(state.planError, agentName, null),
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
          // Fresh result supersedes any stale read-error banner for
          // this agent; plan-side error is cleared alongside because
          // the plan status below is also updated.
          resultError: setMap(state.resultError, agentName, null),
          planError: setMap(state.planError, agentName, null),
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
        // Fresh write supersedes any stale plan-read error banner.
        planError: setMap(state.planError, agentName, null),
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
  /** True while either plan or result is in-flight for this agent. */
  loading: boolean
  /** Plan fetch in-flight. */
  planLoading: boolean
  /** Result fetch in-flight. */
  resultLoading: boolean
  /**
   * First non-null error across plan/result (plan wins if both set)
   * -- keeps the single-banner UI consumers working without forcing
   * them to reconcile two sources. Granular callers should read
   * ``planError`` / ``resultError`` directly.
   */
  error: string | null
  planError: string | null
  resultError: string | null
}

/**
 * Subscribe to the training state for a single agent. Uses
 * ``useShallow`` so re-renders only fire when one of the underlying
 * fields changes, not on every store update.
 */
export function useTrainingForAgent(agentName: string): TrainingForAgent {
  return useTrainingStore(
    useShallow((state): TrainingForAgent => {
      const planError = state.planError[agentName] ?? null
      const resultError = state.resultError[agentName] ?? null
      const planLoading = state.planLoading[agentName] ?? false
      const resultLoading = state.resultLoading[agentName] ?? false
      return {
        plan: state.plansByAgent[agentName] ?? null,
        result: state.resultsByAgent[agentName] ?? null,
        loading: planLoading || resultLoading,
        planLoading,
        resultLoading,
        error: planError ?? resultError,
        planError,
        resultError,
      }
    }),
  )
}
