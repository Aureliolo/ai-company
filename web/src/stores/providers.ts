import { create } from 'zustand'
import {
  listProviders,
  getProvider,
  getProviderModels,
  getProviderHealth,
  createProvider as apiCreateProvider,
  createFromPreset as apiCreateFromPreset,
  updateProvider as apiUpdateProvider,
  deleteProvider as apiDeleteProvider,
  testConnection as apiTestConnection,
  listPresets,
  discoverModels as apiDiscoverModels,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { normalizeProviders, type ProviderWithName } from '@/utils/providers'
import type {
  CreateFromPresetRequest,
  CreateProviderRequest,
  DiscoverModelsResponse,
  ProviderConfig,
  ProviderHealthStatus,
  ProviderHealthSummary,
  ProviderModelConfig,
  ProviderPreset,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateProviderRequest,
} from '@/api/types'
import { useToastStore } from '@/stores/toast'
import type { ProviderSortKey } from '@/utils/providers'

interface ProvidersState {
  // ── List view ──
  providers: readonly ProviderWithName[]
  healthMap: Record<string, ProviderHealthSummary>
  listLoading: boolean
  listError: string | null

  // ── Filters ──
  searchQuery: string
  healthFilter: ProviderHealthStatus | null
  sortBy: ProviderSortKey
  sortDirection: 'asc' | 'desc'

  // ── Detail view ──
  selectedProvider: ProviderWithName | null
  selectedProviderModels: readonly ProviderModelConfig[]
  selectedProviderHealth: ProviderHealthSummary | null
  detailLoading: boolean
  detailError: string | null

  // ── CRUD / mutations ──
  presets: readonly ProviderPreset[]
  presetsLoading: boolean
  presetsError: string | null
  testConnectionResult: TestConnectionResponse | null
  testingConnection: boolean
  discoveringModels: boolean
  mutating: boolean

  // ── Actions ──
  fetchProviders: () => Promise<void>
  fetchProviderDetail: (name: string) => Promise<void>
  fetchPresets: () => Promise<void>
  createProvider: (data: CreateProviderRequest) => Promise<ProviderConfig | null>
  createFromPreset: (data: CreateFromPresetRequest) => Promise<ProviderConfig | null>
  updateProvider: (name: string, data: UpdateProviderRequest) => Promise<ProviderConfig | null>
  deleteProvider: (name: string) => Promise<boolean>
  testConnection: (name: string, data?: TestConnectionRequest) => Promise<TestConnectionResponse | null>
  discoverModels: (name: string, presetHint?: string) => Promise<DiscoverModelsResponse | null>
  clearTestResult: () => void
  clearDetail: () => void
  setSearchQuery: (q: string) => void
  setHealthFilter: (h: ProviderHealthStatus | null) => void
  setSortBy: (key: ProviderSortKey) => void
  setSortDirection: (dir: 'asc' | 'desc') => void
}

// Track latest request IDs to prevent stale responses
let _listRequestId = 0
let _detailRequestName = ''

export const useProvidersStore = create<ProvidersState>()((set, get) => ({
  // ── Defaults ──
  providers: [],
  healthMap: {},
  listLoading: false,
  listError: null,

  searchQuery: '',
  healthFilter: null,
  sortBy: 'name',
  sortDirection: 'asc',

  selectedProvider: null,
  selectedProviderModels: [],
  selectedProviderHealth: null,
  detailLoading: false,
  detailError: null,

  presets: [],
  presetsLoading: false,
  presetsError: null,
  testConnectionResult: null,
  testingConnection: false,
  discoveringModels: false,
  mutating: false,

  // ── List actions ──

  fetchProviders: async () => {
    // Skip if a CRUD mutation is in flight
    if (get().mutating) return

    const requestId = ++_listRequestId
    set({ listLoading: true, listError: null })
    try {
      const record = await listProviders()
      if (requestId !== _listRequestId) return
      const providers = normalizeProviders(record)
      set({ providers })

      // Fetch health in parallel (best-effort, with logging)
      const names = providers.map((p) => p.name)
      const healthResults = await Promise.allSettled(
        names.map((name) => getProviderHealth(name)),
      )
      if (requestId !== _listRequestId) return
      const healthMap: Record<string, ProviderHealthSummary> = {}
      for (let i = 0; i < names.length; i++) {
        const result = healthResults[i]!
        if (result.status === 'fulfilled') {
          healthMap[names[i]!] = result.value
        } else {
          console.warn(
            `Failed to fetch health for provider "${names[i]}":`,
            sanitizeForLog(result.reason),
          )
        }
      }
      set({ healthMap, listLoading: false })
    } catch (err) {
      if (requestId !== _listRequestId) return
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

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
        console.warn('Failed to load models:', sanitizeForLog(modelsResult.reason))
        partialErrors.push(`models (${getErrorMessage(modelsResult.reason)})`)
      }
      if (healthResult.status === 'rejected') {
        console.warn('Failed to load health:', sanitizeForLog(healthResult.reason))
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

  fetchPresets: async () => {
    // Presets are static backend data -- cache for the session lifetime
    if (get().presets.length > 0) return
    set({ presetsLoading: true, presetsError: null })
    try {
      const presets = await listPresets()
      set({ presets, presetsLoading: false })
    } catch (err) {
      set({ presetsLoading: false, presetsError: getErrorMessage(err) })
    }
  },

  // ── CRUD actions ──

  createProvider: async (data) => {
    set({ mutating: true })
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
      set({ mutating: false })
    }
  },

  createFromPreset: async (data) => {
    set({ mutating: true })
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
      set({ mutating: false })
    }
  },

  updateProvider: async (name, data) => {
    set({ mutating: true })
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
      set({ mutating: false })
    }
  },

  deleteProvider: async (name) => {
    set({ mutating: true })
    try {
      await apiDeleteProvider(name)
      // Remove from local state after successful deletion
      set((state) => ({
        providers: state.providers.filter((p) => p.name !== name),
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
      set({ mutating: false })
    }
  },

  testConnection: async (name, data) => {
    set({ testingConnection: true, testConnectionResult: null })
    try {
      const result = await apiTestConnection(name, data)
      set({ testConnectionResult: result, testingConnection: false })
      return result
    } catch (err) {
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

  discoverModels: async (name, presetHint) => {
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

  // ── Filter setters ──

  setSearchQuery: (q) => set({ searchQuery: q }),
  setHealthFilter: (h) => set({ healthFilter: h }),
  setSortBy: (key) => set({ sortBy: key }),
  setSortDirection: (dir) => set({ sortDirection: dir }),
}))
