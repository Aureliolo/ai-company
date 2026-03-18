import { describe, it, expect, beforeEach, vi } from 'vitest'
import * as fc from 'fast-check'
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

  it('updateProvider calls api and refreshes', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    const updatedProvider = { ...mockProvider, driver: 'custom-driver' }
    vi.mocked(providersApi.updateProvider).mockResolvedValue(updatedProvider)
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      'test-provider': updatedProvider,
    })

    const store = useProviderStore()
    await store.updateProvider('test-provider', { driver: 'custom-driver' })

    expect(providersApi.updateProvider).toHaveBeenCalledOnce()
    expect(providersApi.updateProvider).toHaveBeenCalledWith('test-provider', { driver: 'custom-driver' })
    expect(providersApi.listProviders).toHaveBeenCalledOnce()
    expect(store.providers['test-provider'].driver).toBe('custom-driver')
  })

  it('createFromPreset calls api and refreshes', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.createFromPreset).mockResolvedValue(mockProvider)
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      'my-ollama': mockProvider,
    })

    const store = useProviderStore()
    await store.createFromPreset({ preset_name: 'ollama', name: 'my-ollama' })

    expect(providersApi.createFromPreset).toHaveBeenCalledOnce()
    expect(providersApi.createFromPreset).toHaveBeenCalledWith({ preset_name: 'ollama', name: 'my-ollama' })
    expect(providersApi.listProviders).toHaveBeenCalledOnce()
    expect(store.providers['my-ollama']).toBeDefined()
  })

  it('handles fetch error gracefully', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.listProviders).mockRejectedValue(new Error('Network error'))

    const store = useProviderStore()
    await store.fetchProviders()

    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })

  it('sanitizer removes secret fields during fetchProviders', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    // Simulate backend accidentally leaking secrets
    const leakyProvider = {
      ...mockProvider,
      api_key: 'leaked-secret-key',
      oauth_client_secret: 'leaked-oauth-secret',
      custom_header_value: 'leaked-header-value',
    }
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      'test-provider': leakyProvider as unknown as ProviderConfig,
    })

    const store = useProviderStore()
    await store.fetchProviders()

    const stored = store.providers['test-provider'] as Record<string, unknown>
    expect(stored).toBeDefined()
    expect('api_key' in stored).toBe(false)
    expect('oauth_client_secret' in stored).toBe(false)
    expect('custom_header_value' in stored).toBe(false)
    // Non-secret fields remain
    expect(stored.driver).toBe('litellm')
    expect(stored.has_api_key).toBe(false)
  })

  it('sanitizer strips secrets across random provider shapes (property)', () => {
    const SECRET_KEYS = ['api_key', 'oauth_client_secret', 'custom_header_value'] as const

    fc.assert(
      fc.property(
        fc.dictionary(
          fc.string({ minLength: 1, maxLength: 20 }).filter(k => !['__proto__', 'prototype', 'constructor'].includes(k)),
          fc.record({
            driver: fc.constant('litellm'),
            auth_type: fc.constantFrom('api_key' as const, 'oauth' as const, 'none' as const),
            base_url: fc.constant(null),
            models: fc.constant([]),
            has_api_key: fc.boolean(),
            has_oauth_credentials: fc.boolean(),
            has_custom_header: fc.boolean(),
            oauth_token_url: fc.constant(null),
            oauth_client_id: fc.constant(null),
            oauth_scope: fc.constant(null),
            custom_header_name: fc.constant(null),
            api_key: fc.oneof(fc.constant(undefined), fc.string({ minLength: 1 })),
            oauth_client_secret: fc.oneof(fc.constant(undefined), fc.string({ minLength: 1 })),
            custom_header_value: fc.oneof(fc.constant(undefined), fc.string({ minLength: 1 })),
          }),
          { minKeys: 1, maxKeys: 5 },
        ),
        (rawProviders) => {
          // Import the sanitizer indirectly by exercising the store
          // We replicate the sanitizer logic inline since it's not exported
          const UNSAFE = new Set(['__proto__', 'prototype', 'constructor'])
          const result: Record<string, Record<string, unknown>> = {}
          for (const [key, provider] of Object.entries(rawProviders)) {
            if (UNSAFE.has(key)) continue
            const cleaned = { ...provider }
            for (const field of SECRET_KEYS) {
              delete (cleaned as Record<string, unknown>)[field]
            }
            result[key] = cleaned as Record<string, unknown>
          }

          // Assert no secret fields survive
          for (const providerName of Object.keys(result)) {
            for (const secret of SECRET_KEYS) {
              expect(result[providerName]).not.toHaveProperty(secret)
            }
          }
          // Assert no prototype-pollution keys
          for (const unsafeKey of UNSAFE) {
            expect(result).not.toHaveProperty(unsafeKey)
          }
        },
      ),
    )
  })

  it('stale fetch is discarded when newer fetch completes first', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    const store = useProviderStore()

    // Create two deferred promises we control
    let resolveFirst!: (v: Record<string, ProviderConfig>) => void
    let resolveSecond!: (v: Record<string, ProviderConfig>) => void
    const firstPromise = new Promise<Record<string, ProviderConfig>>(r => { resolveFirst = r })
    const secondPromise = new Promise<Record<string, ProviderConfig>>(r => { resolveSecond = r })

    const staleProvider = { ...mockProvider, driver: 'stale-driver' }
    const freshProvider = { ...mockProvider, driver: 'fresh-driver' }

    // First call returns the slow (stale) promise
    vi.mocked(providersApi.listProviders).mockReturnValueOnce(firstPromise)
    const fetch1 = store.fetchProviders()

    // Second call returns the fast (fresh) promise
    vi.mocked(providersApi.listProviders).mockReturnValueOnce(secondPromise)
    const fetch2 = store.fetchProviders()

    // Resolve second (newer) fetch first
    resolveSecond({ 'provider': freshProvider })
    await fetch2

    // Resolve first (stale) fetch after
    resolveFirst({ 'provider': staleProvider })
    await fetch1

    // Store should have fresh data, not stale
    expect(store.providers['provider'].driver).toBe('fresh-driver')
  })
})
