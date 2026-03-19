import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSetupStatus = vi.fn()
const mockListTemplates = vi.fn()
const mockCompleteSetup = vi.fn()

vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: (...args: unknown[]) => mockGetSetupStatus(...args),
  listTemplates: (...args: unknown[]) => mockListTemplates(...args),
  completeSetup: (...args: unknown[]) => mockCompleteSetup(...args),
}))

import { useSetupStore } from '@/stores/setup'
import { MIN_PASSWORD_LENGTH } from '@/utils/constants'

describe('useSetupStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('minPasswordLength', () => {
    it('falls back to MIN_PASSWORD_LENGTH before status is loaded', () => {
      const store = useSetupStore()
      expect(store.minPasswordLength).toBe(MIN_PASSWORD_LENGTH)
    })

    it('uses server value when it exceeds the constant', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: true,
        needs_setup: true,
        has_providers: false,
        min_password_length: 20,
      })

      const store = useSetupStore()
      await store.fetchStatus()
      expect(store.minPasswordLength).toBe(20)
    })

    it('clamps to MIN_PASSWORD_LENGTH when server value is lower', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: true,
        needs_setup: true,
        has_providers: false,
        min_password_length: 4,
      })

      const store = useSetupStore()
      await store.fetchStatus()
      expect(store.minPasswordLength).toBe(MIN_PASSWORD_LENGTH)
    })
  })
})
