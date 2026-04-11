import { create } from 'zustand'

import {
  getScalingDecisions,
  getScalingSignals,
  getScalingStrategies,
  triggerScalingEvaluation,
  type ScalingDecisionResponse,
  type ScalingSignalResponse,
  type ScalingStrategyResponse,
} from '@/api/endpoints/scaling'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import type { WsEvent } from '@/api/types'

const log = createLogger('scaling')

interface ScalingState {
  // Data
  strategies: readonly ScalingStrategyResponse[]
  decisions: readonly ScalingDecisionResponse[]
  signals: readonly ScalingSignalResponse[]
  totalDecisions: number

  // UI state
  loading: boolean
  error: string | null
  evaluating: boolean

  // Actions
  fetchAll: () => Promise<void>
  fetchStrategies: () => Promise<void>
  fetchDecisions: () => Promise<void>
  fetchSignals: () => Promise<void>
  evaluateNow: () => Promise<ScalingDecisionResponse[]>
  updateFromWsEvent: (event: WsEvent) => void
}

export const useScalingStore = create<ScalingState>()((set, get) => ({
  strategies: [],
  decisions: [],
  signals: [],
  totalDecisions: 0,
  loading: false,
  error: null,
  evaluating: false,

  fetchAll: async () => {
    set({ loading: true, error: null })
    try {
      const prev = get()
      const [strategiesR, decisionsR, signalsR] = await Promise.allSettled([
        getScalingStrategies(),
        getScalingDecisions({ limit: 50 }),
        getScalingSignals(),
      ])

      const strategies =
        strategiesR.status === 'fulfilled'
          ? strategiesR.value
          : prev.strategies
      const decisionsResult =
        decisionsR.status === 'fulfilled'
          ? decisionsR.value
          : { data: prev.decisions, total: prev.totalDecisions }
      const signals =
        signalsR.status === 'fulfilled' ? signalsR.value : prev.signals

      const errors = [strategiesR, decisionsR, signalsR]
        .filter((r) => r.status === 'rejected')
        .map((r) => (r as PromiseRejectedResult).reason)
      const errorMsg =
        errors.length > 0
          ? errors.map((e) => getErrorMessage(e)).join('; ')
          : null

      set({
        strategies,
        decisions: decisionsResult.data,
        totalDecisions: decisionsResult.total,
        signals,
        loading: false,
        error: errorMsg,
      })
    } catch (err) {
      log.error('Failed to fetch scaling data', err)
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchStrategies: async () => {
    try {
      const strategies = await getScalingStrategies()
      set({ strategies })
    } catch (err) {
      log.error('Failed to fetch strategies', err)
    }
  },

  fetchDecisions: async () => {
    try {
      const result = await getScalingDecisions({ limit: 50 })
      set({ decisions: result.data, totalDecisions: result.total })
    } catch (err) {
      log.error('Failed to fetch decisions', err)
    }
  },

  fetchSignals: async () => {
    try {
      const signals = await getScalingSignals()
      set({ signals })
    } catch (err) {
      log.error('Failed to fetch signals', err)
    }
  },

  evaluateNow: async () => {
    set({ evaluating: true })
    try {
      const decisions = await triggerScalingEvaluation()
      // Refresh all data after evaluation.
      await get().fetchAll()
      set({ evaluating: false })
      return decisions
    } catch (err) {
      log.error('Failed to trigger evaluation', err)
      set({ evaluating: false, error: getErrorMessage(err) })
      return []
    }
  },

  updateFromWsEvent: (event: WsEvent) => {
    log.debug('Scaling WS event', event.event_type)
    void (async () => {
      try {
        await Promise.all([
          get().fetchDecisions(),
          get().fetchSignals(),
        ])
      } catch (err) {
        log.error('WS event refresh failed', err)
      }
    })()
  },
}))
