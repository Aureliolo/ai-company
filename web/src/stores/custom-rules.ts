import { create } from 'zustand'

import {
  createCustomRule,
  deleteCustomRule,
  listCustomRules,
  listMetrics,
  previewRule,
  toggleCustomRule,
  updateCustomRule,
  type CreateCustomRuleRequest,
  type CustomRule,
  type MetricDescriptor,
  type PreviewRequest,
  type PreviewResult,
} from '@/api/endpoints/custom-rules'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('custom-rules')

let _listRequestToken = 0

function isStaleListRequest(token: number): boolean {
  return _listRequestToken !== token
}

interface CustomRulesState {
  // Data
  rules: readonly CustomRule[]
  metrics: readonly MetricDescriptor[]

  // UI state
  loading: boolean
  error: string | null
  metricsLoading: boolean
  metricsError: string | null
  submitting: boolean

  // Actions
  fetchRules: () => Promise<void>
  fetchMetrics: () => Promise<void>
  createRule: (data: CreateCustomRuleRequest) => Promise<CustomRule>
  updateRule: (
    id: string,
    data: Partial<CreateCustomRuleRequest>,
  ) => Promise<CustomRule>
  deleteRule: (id: string) => Promise<void>
  toggleRule: (id: string) => Promise<CustomRule>
  previewRule: (data: PreviewRequest) => Promise<PreviewResult>
}

export const useCustomRulesStore = create<CustomRulesState>()((set) => ({
  rules: [],
  metrics: [],
  loading: false,
  error: null,
  metricsLoading: false,
  metricsError: null,
  submitting: false,

  fetchRules: async () => {
    const token = ++_listRequestToken
    set({ loading: true, error: null })
    try {
      const rules = await listCustomRules()
      if (isStaleListRequest(token)) return
      set({ rules, loading: false })
    } catch (err) {
      if (isStaleListRequest(token)) return
      log.error('Failed to fetch custom rules', err)
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchMetrics: async () => {
    set({ metricsLoading: true, metricsError: null })
    try {
      const metrics = await listMetrics()
      set({ metrics, metricsLoading: false })
    } catch (err) {
      log.error('Failed to fetch metrics', err)
      set({
        metricsLoading: false,
        metricsError: getErrorMessage(err),
      })
    }
  },

  createRule: async (data) => {
    set({ submitting: true })
    try {
      const rule = await createCustomRule(data)
      set((state) => ({
        rules: [...state.rules, rule],
        submitting: false,
      }))
      return rule
    } catch (err) {
      set({ submitting: false })
      throw err
    }
  },

  updateRule: async (id, data) => {
    set({ submitting: true })
    try {
      const updated = await updateCustomRule(id, data)
      set((state) => ({
        rules: state.rules.map((r) =>
          r.id === id ? updated : r,
        ),
        submitting: false,
      }))
      return updated
    } catch (err) {
      set({ submitting: false })
      throw err
    }
  },

  deleteRule: async (id) => {
    try {
      await deleteCustomRule(id)
      set((state) => ({
        rules: state.rules.filter((r) => r.id !== id),
      }))
    } catch (err) {
      log.error('Failed to delete rule', err)
      throw err
    }
  },

  toggleRule: async (id) => {
    try {
      const toggled = await toggleCustomRule(id)
      set((state) => ({
        rules: state.rules.map((r) =>
          r.id === id ? toggled : r,
        ),
      }))
      return toggled
    } catch (err) {
      log.error('Failed to toggle rule', err)
      throw err
    }
  },

  previewRule: async (data) => {
    return previewRule(data)
  },
}))
