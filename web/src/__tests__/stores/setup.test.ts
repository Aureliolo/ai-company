import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSetupStatus = vi.fn()
const mockListTemplates = vi.fn()
const mockCompleteSetup = vi.fn()
const mockGetAgents = vi.fn()
const mockUpdateAgentModel = vi.fn()

vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: (...args: unknown[]) => mockGetSetupStatus(...args),
  listTemplates: (...args: unknown[]) => mockListTemplates(...args),
  completeSetup: (...args: unknown[]) => mockCompleteSetup(...args),
  getAgents: (...args: unknown[]) => mockGetAgents(...args),
  updateAgentModel: (...args: unknown[]) => mockUpdateAgentModel(...args),
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

  describe('syncCompletionFromStatus', () => {
    it('maps backend status fields to step completion', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: true,
        has_company: true,
        has_agents: false,
        min_password_length: 12,
      })

      const store = useSetupStore()
      await store.fetchStatus()

      expect(store.isStepComplete('admin')).toBe(true)
      expect(store.isStepComplete('provider')).toBe(true)
      expect(store.isStepComplete('company')).toBe(true)
      expect(store.isStepComplete('review')).toBe(false)
    })

    it('marks welcome as complete when currentStep > 0', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: false,
        has_company: false,
        has_agents: false,
        min_password_length: 12,
      })

      const store = useSetupStore()
      store.currentStep = 2
      await store.fetchStatus()

      expect(store.isStepComplete('welcome')).toBe(true)
    })

    it('leaves welcome incomplete when currentStep is 0', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: true,
        needs_setup: true,
        has_providers: false,
        has_company: false,
        has_agents: false,
        min_password_length: 12,
      })

      const store = useSetupStore()
      await store.fetchStatus()

      expect(store.isStepComplete('welcome')).toBe(false)
    })

    it('returns false for all steps before any sync', () => {
      const store = useSetupStore()

      expect(store.isStepComplete('welcome')).toBe(false)
      expect(store.isStepComplete('admin')).toBe(false)
      expect(store.isStepComplete('provider')).toBe(false)
      expect(store.isStepComplete('company')).toBe(false)
      expect(store.isStepComplete('review')).toBe(false)
    })

    it('enforces sequential ordering (company without provider is incomplete)', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: false,
        has_company: true,
        has_agents: false,
        min_password_length: 12,
      })

      const store = useSetupStore()
      await store.fetchStatus()

      expect(store.isStepComplete('admin')).toBe(true)
      expect(store.isStepComplete('provider')).toBe(false)
      // Company exists in backend but provider is missing, so
      // the stepper must not show company as done.
      expect(store.isStepComplete('company')).toBe(false)
      expect(store.isStepComplete('review')).toBe(false)
    })

    it('enforces sequential ordering (agent without admin is incomplete)', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: true,
        needs_setup: true,
        has_providers: true,
        has_company: true,
        has_agents: true,
        min_password_length: 12,
      })

      const store = useSetupStore()
      await store.fetchStatus()

      // Nothing should be complete because admin is not done.
      expect(store.isStepComplete('admin')).toBe(false)
      expect(store.isStepComplete('provider')).toBe(false)
      expect(store.isStepComplete('company')).toBe(false)
      expect(store.isStepComplete('review')).toBe(false)
    })

    it('correctly re-syncs when status regresses (provider deleted)', async () => {
      // First fetch: provider exists
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: true,
        has_company: false,
        has_agents: false,
        min_password_length: 12,
      })

      const store = useSetupStore()
      await store.fetchStatus()
      expect(store.isStepComplete('provider')).toBe(true)

      // Second fetch: provider deleted
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: false,
        has_company: false,
        has_agents: false,
        min_password_length: 12,
      })

      await store.fetchStatus()
      expect(store.isStepComplete('provider')).toBe(false)
    })
  })

  describe('fetchAgents', () => {
    it('populates agents on success', async () => {
      const fakeAgents = [
        {
          name: 'agent-ceo',
          role: 'CEO',
          department: 'executive',
          level: 'senior',
          model_provider: 'test-provider',
          model_id: 'test-large-001',
          tier: 'large',
          personality_preset: 'visionary_leader',
        },
        {
          name: 'agent-dev',
          role: 'Developer',
          department: 'engineering',
          level: 'mid',
          model_provider: 'test-provider',
          model_id: 'test-small-001',
          tier: 'small',
          personality_preset: 'pragmatic_builder',
        },
      ]
      mockGetAgents.mockResolvedValue(fakeAgents)

      const store = useSetupStore()
      await store.fetchAgents()

      expect(store.agents).toEqual(fakeAgents)
      expect(store.error).toBeNull()
    })

    it('sets error on failure and re-throws', async () => {
      mockGetAgents.mockRejectedValue(new Error('Network error'))

      const store = useSetupStore()
      await expect(store.fetchAgents()).rejects.toThrow('Network error')

      expect(store.agents).toEqual([])
      expect(store.error).toBe('Network error')
    })
  })

  describe('updateAgentModel', () => {
    it('replaces the agent at the given index on success', async () => {
      const store = useSetupStore()
      store.agents = [
        {
          name: 'agent-ceo',
          role: 'CEO',
          department: 'executive',
          level: 'senior',
          model_provider: 'test-provider',
          model_id: 'test-large-001',
          tier: 'large',
          personality_preset: 'visionary_leader',
        },
      ]

      const updatedAgent = {
        name: 'agent-ceo',
        role: 'CEO',
        department: 'executive',
        level: 'senior',
        model_provider: 'other-provider',
        model_id: 'other-model-001',
        tier: 'large',
        personality_preset: 'visionary_leader',
      }
      mockUpdateAgentModel.mockResolvedValue(updatedAgent)

      await store.updateAgentModel(0, 'other-provider', 'other-model-001')

      expect(store.agents[0].model_provider).toBe('other-provider')
      expect(store.agents[0].model_id).toBe('other-model-001')
      expect(store.error).toBeNull()
    })

    it('leaves agents unchanged when index is out of bounds', async () => {
      const store = useSetupStore()
      const originalAgent = {
        name: 'agent-ceo',
        role: 'CEO',
        department: 'executive',
        level: 'senior',
        model_provider: 'test-provider',
        model_id: 'test-large-001',
        tier: 'large',
        personality_preset: 'visionary_leader',
      }
      store.agents = [originalAgent]

      const updatedAgent = { ...originalAgent, model_provider: 'new-prov', model_id: 'new-model' }
      mockUpdateAgentModel.mockResolvedValue(updatedAgent)

      await store.updateAgentModel(5, 'new-prov', 'new-model')

      // Agent at index 0 is unchanged because index 5 is out of bounds.
      expect(store.agents).toHaveLength(1)
      expect(store.agents[0].model_provider).toBe('test-provider')
      expect(mockUpdateAgentModel).not.toHaveBeenCalled()
    })

    it('leaves agents unchanged when index is negative', async () => {
      const store = useSetupStore()
      const originalAgent = {
        name: 'agent-ceo',
        role: 'CEO',
        department: 'executive',
        level: 'senior',
        model_provider: 'test-provider',
        model_id: 'test-large-001',
        tier: 'large',
        personality_preset: 'visionary_leader',
      }
      store.agents = [originalAgent]

      await store.updateAgentModel(-1, 'new-prov', 'new-model')

      expect(store.agents).toHaveLength(1)
      expect(store.agents[0].model_provider).toBe('test-provider')
      expect(mockUpdateAgentModel).not.toHaveBeenCalled()
    })

    it('sets error on failure', async () => {
      const store = useSetupStore()
      store.agents = [
        {
          name: 'agent-ceo',
          role: 'CEO',
          department: 'executive',
          level: 'senior',
          model_provider: 'test-provider',
          model_id: 'test-large-001',
          tier: 'large',
          personality_preset: 'visionary_leader',
        },
      ]
      mockUpdateAgentModel.mockRejectedValue(new Error('Server error'))

      await store.updateAgentModel(0, 'bad-prov', 'bad-model')

      expect(store.error).toBe('Server error')
      // Agent should remain unchanged on error.
      expect(store.agents[0].model_provider).toBe('test-provider')
    })
  })

  describe('markComplete', () => {
    it('marks setup as no longer needed on success', async () => {
      mockGetSetupStatus.mockResolvedValue({
        needs_admin: false,
        needs_setup: true,
        has_providers: true,
        has_company: true,
        has_agents: true,
        min_password_length: 12,
      })
      mockCompleteSetup.mockResolvedValue(undefined)

      const store = useSetupStore()
      await store.fetchStatus()
      expect(store.isSetupNeeded).toBe(true)

      await store.markComplete()

      expect(store.isSetupNeeded).toBe(false)
      expect(store.error).toBeNull()
    })

    it('sets error and re-throws on failure', async () => {
      mockCompleteSetup.mockRejectedValue(new Error('Precondition failed'))

      const store = useSetupStore()
      await expect(store.markComplete()).rejects.toThrow('Precondition failed')
      expect(store.error).toBe('Precondition failed')
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
