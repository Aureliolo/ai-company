import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn(),
  listPresets: vi.fn().mockResolvedValue([]),
}))

describe('ProviderFormDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('exports component without errors', async () => {
    const mod = await import('@/components/providers/ProviderFormDialog.vue')
    expect(mod.default).toBeDefined()
  })

  it('component has expected name', async () => {
    const mod = await import('@/components/providers/ProviderFormDialog.vue')
    expect(mod.default.__name).toBe('ProviderFormDialog')
  })
})
