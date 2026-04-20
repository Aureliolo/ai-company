import { completeSetup } from '@/api/endpoints/setup'
import { createLogger } from '@/lib/logger'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { getErrorMessage } from '@/utils/errors'
import { initialStepsCompleted } from './navigation'
import { DEFAULT_THEME } from './theme'
import type { CompletionSlice, SliceCreator } from './types'

const log = createLogger('setup-wizard:completion')

/** Fresh state for all slices -- used by `reset()` to clear the wizard. */
function getInitialState() {
  return {
    currentStep: 'mode' as const,
    stepOrder: ['mode', 'template', 'company', 'providers', 'agents', 'theme', 'complete'] as const,
    stepsCompleted: initialStepsCompleted(),
    direction: 'forward' as const,
    needsAdmin: false,
    accountCreated: false,
    wizardMode: 'guided' as const,

    templates: [],
    templatesLoading: false,
    templatesError: null,
    selectedTemplate: null,
    comparedTemplates: [],
    templateVariables: {},

    companyName: '',
    companyDescription: '',
    currency: DEFAULT_CURRENCY,
    budgetCapEnabled: false,
    budgetCap: null,
    companyResponse: null,
    companyLoading: false,
    companyError: null,

    agents: [],
    agentsLoading: false,
    agentsError: null,
    personalityPresets: [],
    personalityPresetsLoading: false,
    personalityPresetsError: null,

    providers: {},
    presets: [],
    presetsLoading: false,
    presetsError: null,
    probeResults: {},
    probing: false,
    providersLoading: false,
    providersError: null,

    themeSettings: { ...DEFAULT_THEME },

    completing: false,
    completionError: null,
  }
}

export const createCompletionSlice: SliceCreator<CompletionSlice> = (set) => ({
  completing: false,
  completionError: null,

  async completeSetup() {
    set({ completing: true, completionError: null })
    try {
      await completeSetup()
      set({ completing: false })
    } catch (err) {
      log.error('completeSetup failed:', getErrorMessage(err))
      set({ completionError: getErrorMessage(err), completing: false })
      throw err
    }
  },

  reset() {
    set(getInitialState())
  },
})
