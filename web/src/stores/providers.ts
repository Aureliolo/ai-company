import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as providersApi from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import type {
  CreateFromPresetRequest,
  CreateProviderRequest,
  DiscoverModelsResponse,
  ProbePresetResponse,
  ProviderConfig,
  ProviderPreset,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateProviderRequest,
} from '@/api/types'

const UNSAFE_KEYS = new Set(['__proto__', 'prototype', 'constructor'])
const SECRET_FIELDS = new Set(['api_key', 'oauth_client_secret', 'custom_header_value'])

/** Strip prototype-pollution keys and any accidentally-serialized secrets. */
function sanitizeProviders(raw: Record<string, ProviderConfig>): Record<string, ProviderConfig> {
  const result = Object.create(null) as Record<string, ProviderConfig>
  for (const [key, provider] of Object.entries(raw)) {
    if (UNSAFE_KEYS.has(key)) continue
    const cleaned = { ...provider }
    for (const field of SECRET_FIELDS) {
      if (field in cleaned) {
        delete (cleaned as Record<string, unknown>)[field]
      }
    }
    result[key] = cleaned
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
    error.value = null
    try {
      presets.value = await providersApi.listPresets()
    } catch (err) {
      error.value = getErrorMessage(err)
    }
  }

  async function createProvider(data: CreateProviderRequest) {
    try {
      await providersApi.createProvider(data)
      await fetchProviders()
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  async function updateProvider(name: string, data: UpdateProviderRequest) {
    try {
      await providersApi.updateProvider(name, data)
      await fetchProviders()
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  async function deleteProvider(name: string) {
    try {
      await providersApi.deleteProvider(name)
      await fetchProviders()
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  async function testConnectionAction(name: string, data?: TestConnectionRequest): Promise<TestConnectionResponse> {
    return await providersApi.testConnection(name, data)
  }

  async function createFromPreset(data: CreateFromPresetRequest) {
    try {
      await providersApi.createFromPreset(data)
      await fetchProviders()
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  /** Probe is best-effort -- errors propagate to caller, not stored in error.value. */
  async function probePresetAction(presetName: string): Promise<ProbePresetResponse> {
    return await providersApi.probePreset(presetName)
  }

  async function discoverModelsAction(name: string): Promise<DiscoverModelsResponse> {
    try {
      const result = await providersApi.discoverModels(name)
      await fetchProviders()
      return result
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
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
    probePreset: probePresetAction,
    discoverModels: discoverModelsAction,
  }
})
