import {
  getProvider,
  getProviderModels,
  getProviderHealth,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import type { ProvidersSet } from './types'

const log = createLogger('providers')

let _detailRequestId = 0

export function createDetailActions(set: ProvidersSet) {
  return {
    fetchProviderDetail: async (name: string) => {
      const requestId = ++_detailRequestId
      set({ detailLoading: true, detailError: null })
      try {
        const [providerResult, modelsResult, healthResult] =
          await Promise.allSettled([
            getProvider(name),
            getProviderModels(name),
            getProviderHealth(name),
          ])

        if (requestId !== _detailRequestId) return

        const provider = providerResult.status === 'fulfilled'
          ? { ...providerResult.value, name }
          : null
        if (!provider) {
          const reason = providerResult.status === 'rejected'
            ? providerResult.reason
            : null
          set({
            detailLoading: false,
            detailError: getErrorMessage(reason ?? 'Provider not found'),
            selectedProvider: null,
            selectedProviderModels: [],
            selectedProviderHealth: null,
            testConnectionResult: null,
          })
          return
        }

        const partialErrors: string[] = []
        if (modelsResult.status === 'rejected') {
          const msg = getErrorMessage(modelsResult.reason)
          log.warn('Failed to load models:', msg)
          partialErrors.push(`models (${msg})`)
        }
        if (healthResult.status === 'rejected') {
          const msg = getErrorMessage(healthResult.reason)
          log.warn('Failed to load health:', msg)
          partialErrors.push(`health (${msg})`)
        }

        set({
          selectedProvider: provider,
          selectedProviderModels:
            modelsResult.status === 'fulfilled' ? modelsResult.value : [],
          selectedProviderHealth:
            healthResult.status === 'fulfilled' ? healthResult.value : null,
          detailLoading: false,
          detailError: partialErrors.length > 0
            ? `Some data failed to load: ${partialErrors.join(', ')}`
            : null,
        })
      } catch (err) {
        if (requestId !== _detailRequestId) return
        log.error('Failed to fetch provider detail:', getErrorMessage(err))
        set({ detailLoading: false, detailError: getErrorMessage(err) })
      }
    },

    clearDetail: () => {
      _detailRequestId++ // invalidate in-flight requests
      set({
        selectedProvider: null,
        selectedProviderModels: [],
        selectedProviderHealth: null,
        detailLoading: false,
        detailError: null,
        testConnectionResult: null,
        testingConnection: false,
      })
    },
  }
}
