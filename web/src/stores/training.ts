import { create } from 'zustand'

import {
  createTrainingPlan,
  executeTrainingPlan,
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

  fetchResult: (agentName: string) => Promise<void>
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

export const useTrainingStore = create<TrainingState>()((set) => ({
  plansByAgent: {},
  resultsByAgent: {},
  loading: {},
  error: {},

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
      }))
    } catch (err) {
      const message = getErrorMessage(err)
      log.error('fetchResult failed:', sanitizeForLog(agentName), err)
      set((state) => ({
        loading: setMap(state.loading, agentName, false),
        error: setMap(state.error, agentName, message),
      }))
    }
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
      log.error('createPlan failed:', sanitizeForLog(agentName), err)
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
      set((state) => ({
        resultsByAgent: setMap(state.resultsByAgent, agentName, result),
      }))
      useToastStore.getState().add({
        variant: 'success',
        title: 'Training executed',
      })
      return result
    } catch (err) {
      log.error('executePlan failed:', sanitizeForLog(agentName), err)
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
      log.error('previewPlan failed:', sanitizeForLog(agentName), err)
      useToastStore.getState().add({
        variant: 'error',
        title: 'Preview failed',
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
      log.error('updateOverrides failed:', sanitizeForLog(agentName), err)
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to save overrides',
        description: getErrorMessage(err),
      })
      return null
    }
  },
}))

export function useTrainingForAgent(agentName: string) {
  return useTrainingStore((state) => ({
    plan: state.plansByAgent[agentName] ?? null,
    result: state.resultsByAgent[agentName] ?? null,
    loading: state.loading[agentName] ?? false,
    error: state.error[agentName] ?? null,
  }))
}
