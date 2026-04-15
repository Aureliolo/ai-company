import { useCallback, useEffect, useState } from 'react'

import {
  listAllRules,
  type CustomRule,
  type MetricDescriptor,
  type RuleListItem,
} from '@/api/endpoints/custom-rules'
import { useCustomRulesStore } from '@/stores/custom-rules'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('rules-data')

export interface UseRulesDataReturn {
  /** All rules (built-in + custom) from /api/meta/rules. */
  allRules: readonly RuleListItem[]
  /** Custom rules from the dedicated store. */
  customRules: readonly CustomRule[]
  /** Available metric descriptors. */
  metrics: readonly MetricDescriptor[]
  /** Whether data is loading. */
  loading: boolean
  /** Error message, if any. */
  error: string | null
  /** Whether metrics are loading. */
  metricsLoading: boolean
  /** Refresh all rule data. */
  refresh: () => Promise<void>
}

export function useRulesData(): UseRulesDataReturn {
  const customRules = useCustomRulesStore((s) => s.rules)
  const metrics = useCustomRulesStore((s) => s.metrics)
  const customLoading = useCustomRulesStore((s) => s.loading)
  const customError = useCustomRulesStore((s) => s.error)
  const metricsLoading = useCustomRulesStore((s) => s.metricsLoading)

  const [allRules, setAllRules] = useState<readonly RuleListItem[]>([])
  const [mergedLoading, setMergedLoading] = useState(false)
  const [mergedError, setMergedError] = useState<string | null>(null)

  const fetchMergedRules = useCallback(async () => {
    setMergedLoading(true)
    setMergedError(null)
    try {
      const rules = await listAllRules()
      setAllRules(rules)
    } catch (err) {
      log.error('Failed to fetch merged rules', err)
      setMergedError(getErrorMessage(err))
    } finally {
      setMergedLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    await Promise.all([
      useCustomRulesStore.getState().fetchRules(),
      useCustomRulesStore.getState().fetchMetrics(),
      fetchMergedRules(),
    ])
  }, [fetchMergedRules])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const loading = customLoading || mergedLoading
  const error = customError ?? mergedError

  return {
    allRules,
    customRules,
    metrics,
    loading,
    error,
    metricsLoading,
    refresh,
  }
}
