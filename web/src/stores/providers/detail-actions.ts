import {
  getProvider,
  getProviderModels,
  getProviderHealth,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import type { ProvidersSet } from './types'

const log = createLogger('providers')

let _detailRequestName = ''

export function createDetailActions(set: ProvidersSet) {
  return {
    fetchProviderDetail: async (name: string) => {
      _detailRequestName = name
      set({ detailLoading: true, detailError: null })
      try {
        const [providerResult, modelsResult, healthResult] =
          await Promise.allSettled([
            getProvider(name),
            getProviderModels(name),
            getProviderHealth(name),
          ])

        if (_detailRequestName !== name) return

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
          log.warn('Failed to load models:', modelsResult.reason)
          partialErrors.push(`models (${getErrorMessage(modelsResult.reason)})`)
        }
        if (healthResult.status === 'rejected') {
          log.warn('Failed to load health:', healthResult.reason)
          partialErrors.push(`health (${getErrorMessage(healthResult.reason)})`)
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
        if (_detailRequestName !== name) return
        set({ detailLoading: false, detailError: getErrorMessage(err) })
      }
    },

    clearDetail: () => {
      _detailRequestName = ''
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
