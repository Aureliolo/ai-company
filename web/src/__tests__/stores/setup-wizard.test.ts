import { useSetupWizardStore } from '@/stores/setup-wizard'
import type { SeniorityLevel } from '@/api/types'

vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn(),
  listTemplates: vi.fn(),
  createCompany: vi.fn(),
  getAgents: vi.fn(),
  updateAgentModel: vi.fn(),
  updateAgentName: vi.fn(),
  randomizeAgentName: vi.fn(),
  getAvailableLocales: vi.fn(),
  getNameLocales: vi.fn(),
  saveNameLocales: vi.fn(),
  completeSetup: vi.fn(),
}))

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn(),
  listPresets: vi.fn(),
  createFromPreset: vi.fn(),
  testConnection: vi.fn(),
  probePreset: vi.fn(),
}))

function resetStore() {
  useSetupWizardStore.getState().reset()
}

describe('setup wizard store', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  describe('initialization', () => {
    it('initializes with template as first step when needsAdmin is false', () => {
      const state = useSetupWizardStore.getState()
      expect(state.needsAdmin).toBe(false)
      expect(state.stepOrder[0]).toBe('template')
      expect(state.stepOrder).not.toContain('account')
    })

    it('has all steps completed set to false', () => {
      const state = useSetupWizardStore.getState()
      for (const step of state.stepOrder) {
        expect(state.stepsCompleted[step]).toBe(false)
      }
    })

    it('has EUR as default currency', () => {
      expect(useSetupWizardStore.getState().currency).toBe('EUR')
    })

    it('has no template selected', () => {
      expect(useSetupWizardStore.getState().selectedTemplate).toBeNull()
    })
  })

  describe('navigation', () => {
    it('sets current step', () => {
      useSetupWizardStore.getState().setStep('company')
      expect(useSetupWizardStore.getState().currentStep).toBe('company')
    })

    it('sets direction to forward when advancing', () => {
      useSetupWizardStore.getState().setStep('company')
      expect(useSetupWizardStore.getState().direction).toBe('forward')
    })

    it('sets direction to backward when going back', () => {
      useSetupWizardStore.getState().setStep('company')
      useSetupWizardStore.getState().setStep('template')
      expect(useSetupWizardStore.getState().direction).toBe('backward')
    })

    it('marks step as complete', () => {
      useSetupWizardStore.getState().markStepComplete('template')
      expect(useSetupWizardStore.getState().stepsCompleted.template).toBe(true)
    })

    it('marks step as incomplete', () => {
      useSetupWizardStore.getState().markStepComplete('template')
      useSetupWizardStore.getState().markStepIncomplete('template')
      expect(useSetupWizardStore.getState().stepsCompleted.template).toBe(false)
    })

    it('canNavigateTo returns true for first step', () => {
      expect(useSetupWizardStore.getState().canNavigateTo('template')).toBe(true)
    })

    it('canNavigateTo returns false for later steps when prior are incomplete', () => {
      expect(useSetupWizardStore.getState().canNavigateTo('company')).toBe(false)
    })

    it('canNavigateTo returns true when all prior steps are complete', () => {
      useSetupWizardStore.getState().markStepComplete('template')
      expect(useSetupWizardStore.getState().canNavigateTo('company')).toBe(true)
    })

    it('canNavigateTo checks all prior steps', () => {
      useSetupWizardStore.getState().markStepComplete('template')
      // company not complete, so agents should be inaccessible
      expect(useSetupWizardStore.getState().canNavigateTo('agents')).toBe(false)
    })
  })

  describe('dynamic step order', () => {
    it('includes account step when needsAdmin is true', () => {
      useSetupWizardStore.getState().setNeedsAdmin(true)
      const state = useSetupWizardStore.getState()
      expect(state.stepOrder[0]).toBe('account')
      expect(state.stepOrder).toContain('account')
    })

    it('excludes account step when needsAdmin is false', () => {
      useSetupWizardStore.getState().setNeedsAdmin(false)
      const state = useSetupWizardStore.getState()
      expect(state.stepOrder).not.toContain('account')
    })
  })

  describe('template actions', () => {
    it('selects a template', () => {
      useSetupWizardStore.getState().selectTemplate('startup')
      expect(useSetupWizardStore.getState().selectedTemplate).toBe('startup')
    })

    it('toggles compare on', () => {
      useSetupWizardStore.getState().toggleCompare('startup')
      expect(useSetupWizardStore.getState().comparedTemplates).toContain('startup')
    })

    it('toggles compare off', () => {
      useSetupWizardStore.getState().toggleCompare('startup')
      useSetupWizardStore.getState().toggleCompare('startup')
      expect(useSetupWizardStore.getState().comparedTemplates).not.toContain('startup')
    })

    it('limits comparison to 3 templates', () => {
      useSetupWizardStore.getState().toggleCompare('a')
      useSetupWizardStore.getState().toggleCompare('b')
      useSetupWizardStore.getState().toggleCompare('c')
      const added = useSetupWizardStore.getState().toggleCompare('d')
      expect(added).toBe(false)
      expect(useSetupWizardStore.getState().comparedTemplates).toHaveLength(3)
    })

    it('clears comparison', () => {
      useSetupWizardStore.getState().toggleCompare('a')
      useSetupWizardStore.getState().toggleCompare('b')
      useSetupWizardStore.getState().clearComparison()
      expect(useSetupWizardStore.getState().comparedTemplates).toHaveLength(0)
    })

    it('fetches templates from API', async () => {
      const { listTemplates } = await import('@/api/endpoints/setup')
      vi.mocked(listTemplates).mockResolvedValue([
        {
          name: 'startup',
          display_name: 'Tech Startup',
          description: 'A startup template',
          source: 'builtin',
          tags: ['startup'],
          skill_patterns: [],
          variables: [],
        },
      ])

      await useSetupWizardStore.getState().fetchTemplates()

      const state = useSetupWizardStore.getState()
      expect(state.templates).toHaveLength(1)
      expect(state.templates[0]?.name).toBe('startup')
      expect(state.templatesLoading).toBe(false)
      expect(state.templatesError).toBeNull()
    })

    it('sets error on fetch failure', async () => {
      const { listTemplates } = await import('@/api/endpoints/setup')
      vi.mocked(listTemplates).mockRejectedValue(new Error('Network error'))

      await useSetupWizardStore.getState().fetchTemplates()

      const state = useSetupWizardStore.getState()
      // getErrorMessage extracts the message from the Error object
      expect(state.templatesError).toBe('Network error')
      expect(state.templatesLoading).toBe(false)
    })
  })

  describe('company actions', () => {
    it('sets company name', () => {
      useSetupWizardStore.getState().setCompanyName('Acme Corp')
      expect(useSetupWizardStore.getState().companyName).toBe('Acme Corp')
    })

    it('sets currency', () => {
      useSetupWizardStore.getState().setCurrency('USD')
      expect(useSetupWizardStore.getState().currency).toBe('USD')
    })

    it('submits company and stores response', async () => {
      const { createCompany } = await import('@/api/endpoints/setup')
      vi.mocked(createCompany).mockResolvedValue({
        company_name: 'Acme Corp',
        description: null,
        template_applied: 'startup',
        department_count: 3,
        agent_count: 5,
        agents: [
          {
            name: 'CEO',
            role: 'CEO',
            department: 'executive',
            level: 'c_suite' as SeniorityLevel,
            model_provider: 'test-provider',
            model_id: 'test-model',
            tier: 'large',
            personality_preset: 'visionary_leader',
          },
        ],
      })

      useSetupWizardStore.setState({ companyName: 'Acme Corp', selectedTemplate: 'startup' })
      await useSetupWizardStore.getState().submitCompany()

      const state = useSetupWizardStore.getState()
      expect(state.companyResponse).toBeDefined()
      expect(state.companyResponse?.company_name).toBe('Acme Corp')
      expect(state.agents).toHaveLength(1)
      expect(state.companyLoading).toBe(false)
    })
  })

  describe('agent actions', () => {
    it('updates agent name via API', async () => {
      const { updateAgentName } = await import('@/api/endpoints/setup')
      const updatedAgent = {
        name: 'New Name',
        role: 'CEO',
        department: 'executive',
        level: 'c_suite' as SeniorityLevel,
        model_provider: 'p',
        model_id: 'm',
        tier: 'large',
        personality_preset: null,
      }
      vi.mocked(updateAgentName).mockResolvedValue(updatedAgent)

      useSetupWizardStore.setState({
        agents: [{
          name: 'Old Name',
          role: 'CEO',
          department: 'executive',
          level: 'c_suite' as SeniorityLevel,
          model_provider: 'p',
          model_id: 'm',
          tier: 'large',
          personality_preset: null,
        }],
      })

      await useSetupWizardStore.getState().updateAgentName(0, 'New Name')
      expect(useSetupWizardStore.getState().agents[0]?.name).toBe('New Name')
    })
  })

  describe('theme settings', () => {
    it('updates theme setting', () => {
      useSetupWizardStore.getState().setThemeSetting('density', 'dense')
      expect(useSetupWizardStore.getState().themeSettings.density).toBe('dense')
    })

    it('preserves other theme settings when updating one', () => {
      useSetupWizardStore.getState().setThemeSetting('density', 'dense')
      useSetupWizardStore.getState().setThemeSetting('animation', 'spring')
      const state = useSetupWizardStore.getState()
      expect(state.themeSettings.density).toBe('dense')
      expect(state.themeSettings.animation).toBe('spring')
    })
  })

  describe('reset', () => {
    it('resets all state to initial values', () => {
      useSetupWizardStore.setState({
        selectedTemplate: 'startup',
        companyName: 'Acme',
        currency: 'USD',
      })
      useSetupWizardStore.getState().reset()

      const state = useSetupWizardStore.getState()
      expect(state.selectedTemplate).toBeNull()
      expect(state.companyName).toBe('')
      expect(state.currency).toBe('EUR')
    })
  })
})
