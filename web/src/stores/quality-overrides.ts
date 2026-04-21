/**
 * Per-agent quality-score override store.
 *
 * Owns the toast / error UX for the three quality-override endpoints
 * so the {@link QualityScoreOverride} component stays presentational.
 * Follows the canonical store error contract (try/catch -> log + toast
 * -> sentinel return) -- callers MUST NOT wrap these in try/catch.
 *
 * The `getOverride` action specifically does NOT toast on a 404, since
 * "no active override for this agent" is the steady-state for most
 * agents and is communicated through the `null` return.
 */

import { create } from 'zustand'
import {
  clearQualityOverride as apiClear,
  getQualityOverride as apiGet,
  setQualityOverride as apiSet,
} from '@/api/endpoints/quality'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage, isAxiosError } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { OverrideResponse, SetOverrideRequest } from '@/api/types/collaboration'

const log = createLogger('quality-overrides')

interface QualityOverridesState {
  /**
   * Fetch the active override for an agent. A 404 is normal (no active
   * override) and resolves to `null` without toasting. Any other
   * failure (network, 500) toasts an error and returns `null`.
   */
  getOverride: (agentId: string) => Promise<OverrideResponse | null>
  setOverride: (
    agentId: string,
    data: SetOverrideRequest,
  ) => Promise<OverrideResponse | null>
  clearOverride: (agentId: string) => Promise<boolean>
}

export const useQualityOverridesStore = create<QualityOverridesState>()(() => ({
  getOverride: async (agentId) => {
    try {
      return await apiGet(agentId)
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 404) {
        return null
      }
      log.error('Get quality override failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to load quality override',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  setOverride: async (agentId, data) => {
    try {
      const result = await apiSet(agentId, data)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Quality override applied',
      })
      return result
    } catch (err) {
      log.error('Set quality override failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to apply quality override',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  clearOverride: async (agentId) => {
    try {
      await apiClear(agentId)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Quality override cleared',
      })
      return true
    } catch (err) {
      log.error('Clear quality override failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to clear quality override',
        description: getErrorMessage(err),
      })
      return false
    }
  },
}))
