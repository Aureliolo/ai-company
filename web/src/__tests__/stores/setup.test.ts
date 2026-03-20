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
        has_company: false,
        has_agents: false,
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
        has_company: false,
        has_agents: false,
        min_password_length: 4,
      })

      const store = useSetupStore()
      await store.fetchStatus()
      expect(store.minPasswordLength).toBe(MIN_PASSWORD_LENGTH)
    })
  })

  describe('prevStep', () => {
    it('decrements currentStep by one', () => {
      const store = useSetupStore()
      store.currentStep = 3
      store.prevStep()
      expect(store.currentStep).toBe(2)
    })

    it('does not go below 0', () => {
      const store = useSetupStore()
      store.currentStep = 0
      store.prevStep()
      expect(store.currentStep).toBe(0)
    })

    it('decrements from 1 to 0', () => {
      const store = useSetupStore()
      store.currentStep = 1
      store.prevStep()
      expect(store.currentStep).toBe(0)
    })
  })

  describe('setStep', () => {
    it('sets currentStep to the given index', () => {
      const store = useSetupStore()
      store.setStep(3)
      expect(store.currentStep).toBe(3)
    })

    it('clamps to 0 when given a negative index', () => {
      const store = useSetupStore()
      store.setStep(-1)
      expect(store.currentStep).toBe(0)
    })

    it('clamps to maxSteps - 1 when index exceeds bounds', () => {
      const store = useSetupStore()
      store.setStep(10, 5)
      expect(store.currentStep).toBe(4)
    })

    it('allows setting to maxSteps - 1 exactly', () => {
      const store = useSetupStore()
      store.setStep(4, 5)
      expect(store.currentStep).toBe(4)
    })

    it('sets to 0 when maxSteps is not provided and index is 0', () => {
      const store = useSetupStore()
      store.currentStep = 3
      store.setStep(0)
      expect(store.currentStep).toBe(0)
    })
  })
})
