import {
  listPresets,
  createProvider as apiCreateProvider,
  createFromPreset as apiCreateFromPreset,
  updateProvider as apiUpdateProvider,
  deleteProvider as apiDeleteProvider,
  testConnection as apiTestConnection,
  discoverModels as apiDiscoverModels,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import type {
  CreateFromPresetRequest,
  CreateProviderRequest,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateProviderRequest,
} from '@/api/types'
import { useToastStore } from '@/stores/toast'
import type { ProvidersSet, ProvidersGet } from './types'

const log = createLogger('providers')

let _mutationCount = 0

function beginMutation(set: ProvidersSet): void {
  _mutationCount++
  set({ mutating: true })
}

function endMutation(set: ProvidersSet): void {
  _mutationCount = Math.max(0, _mutationCount - 1)
  if (_mutationCount === 0) set({ mutating: false })
}

export function createCrudActions(set: ProvidersSet, get: ProvidersGet) {
  return {
    fetchPresets: async () => {
      // Presets are static backend data -- cache for the session lifetime
      if (get().presets.length > 0) return
      set({ presetsLoading: true, presetsError: null })
      try {
        const presets = await listPresets()
        set({ presets, presetsLoading: false })
      } catch (err) {
        log.warn('Failed to fetch presets:', getErrorMessage(err))
        set({ presetsLoading: false, presetsError: getErrorMessage(err) })
      }
    },

    createProvider: async (data: CreateProviderRequest) => {
      beginMutation(set)
      try {
        const config = await apiCreateProvider(data)
        useToastStore.getState().add({
          variant: 'success',
          title: `Provider "${data.name}" created`,
        })
        await get().fetchProviders()
        return config
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to create provider',
          description: getErrorMessage(err),
        })
        return null
      } finally {
        endMutation(set)
      }
    },

    createFromPreset: async (data: CreateFromPresetRequest) => {
      beginMutation(set)
      try {
        const config = await apiCreateFromPreset(data)
        useToastStore.getState().add({
          variant: 'success',
          title: `Provider "${data.name}" created from preset`,
        })
        await get().fetchProviders()
        return config
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to create provider',
          description: getErrorMessage(err),
        })
        return null
      } finally {
        endMutation(set)
      }
    },

    updateProvider: async (name: string, data: UpdateProviderRequest) => {
      beginMutation(set)
      try {
        const config = await apiUpdateProvider(name, data)
        useToastStore.getState().add({
          variant: 'success',
          title: `Provider "${name}" updated`,
        })
        // Refresh both list and detail if viewing this provider
        await get().fetchProviders()
        if (get().selectedProvider?.name === name) {
          await get().fetchProviderDetail(name)
        }
        return config
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to update provider',
          description: getErrorMessage(err),
        })
        return null
      } finally {
        endMutation(set)
      }
    },

    deleteProvider: async (name: string) => {
      beginMutation(set)
      try {
        await apiDeleteProvider(name)
        // Clear detail view first if we're deleting the selected provider
        // (resets _detailRequestName guard so in-flight fetches are ignored)
        if (get().selectedProvider?.name === name) {
          get().clearDetail()
        }
        // Remove from list and health map
        set((state) => ({
          providers: state.providers.filter((p) => p.name !== name),
          healthMap: Object.fromEntries(
            Object.entries(state.healthMap).filter(([k]) => k !== name),
          ),
        }))
        useToastStore.getState().add({
          variant: 'success',
          title: `Provider "${name}" deleted`,
        })
        return true
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to delete provider',
          description: getErrorMessage(err),
        })
        // Refresh to restore accurate state
        await get().fetchProviders()
        return false
      } finally {
        endMutation(set)
      }
    },

    testConnection: async (name: string, data?: TestConnectionRequest) => {
      const targetProvider = name
      set({ testingConnection: true, testConnectionResult: null })
      try {
        const result = await apiTestConnection(name, data)
        // Drop stale result if user navigated away (clearDetail)
        if (get().selectedProvider?.name !== targetProvider) {
          set({ testingConnection: false })
          return null
        }
        set({ testConnectionResult: result, testingConnection: false })
        return result
      } catch (err) {
        if (get().selectedProvider?.name !== targetProvider) {
          set({ testingConnection: false })
          return null
        }
        const errorResult: TestConnectionResponse = {
          success: false,
          latency_ms: null,
          error: getErrorMessage(err),
          model_tested: null,
        }
        set({ testConnectionResult: errorResult, testingConnection: false })
        return errorResult
      }
    },

    discoverModels: async (name: string, presetHint?: string) => {
      set({ discoveringModels: true })
      try {
        const result = await apiDiscoverModels(name, presetHint)
        useToastStore.getState().add({
          variant: 'success',
          title: `Discovered ${result.discovered_models.length} models`,
        })
        // Refresh detail to show updated models
        if (get().selectedProvider?.name === name) {
          await get().fetchProviderDetail(name)
        }
        return result
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Model discovery failed',
          description: getErrorMessage(err),
        })
        return null
      } finally {
        set({ discoveringModels: false })
      }
    },

    clearTestResult: () => set({ testConnectionResult: null }),
  }
}
