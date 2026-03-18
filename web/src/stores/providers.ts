import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as providersApi from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import type {
  CreateFromPresetRequest,
  CreateProviderRequest,
  ProviderConfig,
  ProviderPreset,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateProviderRequest,
} from '@/api/types'

const UNSAFE_KEYS = new Set(['__proto__', 'prototype', 'constructor'])

/** Strip any accidentally-serialized secrets before storing in reactive state. */
function sanitizeProviders(raw: Record<string, ProviderConfig>): Record<string, ProviderConfig> {
  const result = Object.create(null) as Record<string, ProviderConfig>
  for (const [key, provider] of Object.entries(raw)) {
    if (UNSAFE_KEYS.has(key)) continue
    result[key] = provider
  }
  return result
}

export const useProviderStore = defineStore('providers', () => {
  const providers = ref<Record<string, ProviderConfig>>({})
  const presets = ref<ProviderPreset[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let generation = 0

  async function fetchProviders() {
    loading.value = true
    error.value = null
    const gen = ++generation
    try {
      const raw = await providersApi.listProviders()
      if (gen === generation) {
        providers.value = sanitizeProviders(raw)
      }
    } catch (err) {
      if (gen === generation) {
        error.value = getErrorMessage(err)
      }
    } finally {
      if (gen === generation) {
        loading.value = false
      }
    }
  }

  async function fetchPresets() {
    try {
      presets.value = await providersApi.listPresets()
    } catch (err) {
      error.value = getErrorMessage(err)
    }
  }

  async function createProvider(data: CreateProviderRequest) {
    await providersApi.createProvider(data)
    await fetchProviders()
  }

  async function updateProvider(name: string, data: UpdateProviderRequest) {
    await providersApi.updateProvider(name, data)
    await fetchProviders()
  }

  async function deleteProvider(name: string) {
    await providersApi.deleteProvider(name)
    await fetchProviders()
  }

  async function testConnectionAction(name: string, data?: TestConnectionRequest): Promise<TestConnectionResponse> {
    return await providersApi.testConnection(name, data)
  }

  async function createFromPreset(data: CreateFromPresetRequest) {
    await providersApi.createFromPreset(data)
    await fetchProviders()
  }

  return {
    providers,
    presets,
    loading,
    error,
    fetchProviders,
    fetchPresets,
    createProvider,
    updateProvider,
    deleteProvider,
    testConnection: testConnectionAction,
    createFromPreset,
  }
})
