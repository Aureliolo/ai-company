import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProviderStore } from '@/stores/providers'
import type { ProviderConfig, ProviderPreset } from '@/api/types'

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn(),
  getProvider: vi.fn(),
  getProviderModels: vi.fn(),
  createProvider: vi.fn(),
  updateProvider: vi.fn(),
  deleteProvider: vi.fn(),
  testConnection: vi.fn(),
  listPresets: vi.fn(),
  createFromPreset: vi.fn(),
}))

const mockProvider: ProviderConfig = {
  driver: 'litellm',
  auth_type: 'none',
  base_url: 'http://localhost:11434',
  models: [
    {
      id: 'test-model-001',
      alias: 'medium',
      cost_per_1k_input: 0,
      cost_per_1k_output: 0,
      max_context: 200000,
      estimated_latency_ms: null,
    },
  ],
  has_api_key: false,
  has_oauth_credentials: false,
  has_custom_header: false,
  oauth_token_url: null,
  oauth_client_id: null,
  oauth_scope: null,
  custom_header_name: null,
}

const mockPreset: ProviderPreset = {
  name: 'ollama',
  display_name: 'Ollama',
  description: 'Local LLM inference server',
  driver: 'litellm',
  auth_type: 'none',
  default_base_url: 'http://localhost:11434',
  default_models: [],
}

describe('useProviderStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initializes with empty state', () => {
    const store = useProviderStore()
    expect(store.providers).toEqual({})
    expect(store.presets).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchProviders populates state', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      'test-provider': mockProvider,
    })

    const store = useProviderStore()
    await store.fetchProviders()

    expect(store.providers['test-provider']).toBeDefined()
    expect(store.providers['test-provider'].driver).toBe('litellm')
    expect(store.loading).toBe(false)
  })

  it('fetchPresets populates presets', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

    const store = useProviderStore()
    await store.fetchPresets()

    expect(store.presets).toHaveLength(1)
    expect(store.presets[0].name).toBe('ollama')
  })

  it('createProvider calls api and refreshes', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.createProvider).mockResolvedValue(mockProvider)
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      'new-provider': mockProvider,
    })

    const store = useProviderStore()
    await store.createProvider({
      name: 'new-provider',
      driver: 'litellm',
      auth_type: 'none',
    })

    expect(providersApi.createProvider).toHaveBeenCalledOnce()
    expect(providersApi.listProviders).toHaveBeenCalledOnce()
    expect(store.providers['new-provider']).toBeDefined()
  })

  it('deleteProvider removes from state', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.listProviders).mockResolvedValueOnce({
      'test-provider': mockProvider,
    })

    const store = useProviderStore()
    await store.fetchProviders()
    expect(store.providers['test-provider']).toBeDefined()

    vi.mocked(providersApi.deleteProvider).mockResolvedValue(undefined)
    vi.mocked(providersApi.listProviders).mockResolvedValueOnce({})

    await store.deleteProvider('test-provider')
    expect(providersApi.deleteProvider).toHaveBeenCalledWith('test-provider')
    expect(store.providers['test-provider']).toBeUndefined()
  })

  it('handles fetch error gracefully', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.listProviders).mockRejectedValue(new Error('Network error'))

    const store = useProviderStore()
    await store.fetchProviders()

    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })
})
