/** Setup wizard state management. */

import { create } from 'zustand'
import type {
  ProviderConfig,
  ProviderPreset,
  ProbePresetResponse,
  SetupAgentSummary,
  SetupCompanyResponse,
  TemplateInfoResponse,
  TestConnectionResponse,
} from '@/api/types'
import {
  listTemplates,
  createCompany,
  getAgents,
  updateAgentModel as apiUpdateAgentModel,
  updateAgentName as apiUpdateAgentName,
  randomizeAgentName as apiRandomizeAgentName,
  completeSetup,
} from '@/api/endpoints/setup'
import {
  listProviders,
  listPresets,
  createFromPreset,
  testConnection,
  probePreset,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import type { CurrencyCode } from '@/utils/currencies'

export type WizardStep =
  | 'account'
  | 'template'
  | 'company'
  | 'agents'
  | 'providers'
  | 'theme'
  | 'complete'

const FULL_STEP_ORDER: readonly WizardStep[] = [
  'account', 'template', 'company', 'agents', 'providers', 'theme', 'complete',
]

const STEP_ORDER_NO_ACCOUNT: readonly WizardStep[] = [
  'template', 'company', 'agents', 'providers', 'theme', 'complete',
]

export type ThemeSettings = {
  palette: 'dark' | 'light'
  density: 'dense' | 'balanced' | 'sparse'
  animation: 'minimal' | 'status-driven' | 'spring' | 'instant'
  sidebar: 'rail' | 'collapsible' | 'hidden' | 'compact'
  typography: 'default'
}

const DEFAULT_THEME: ThemeSettings = {
  palette: 'dark',
  density: 'balanced',
  animation: 'status-driven',
  sidebar: 'collapsible',
  typography: 'default',
}

interface SetupWizardState {
  // Navigation
  currentStep: WizardStep
  stepOrder: readonly WizardStep[]
  stepsCompleted: Record<WizardStep, boolean>
  direction: 'forward' | 'backward'
  needsAdmin: boolean
  accountCreated: boolean

  // Template
  templates: TemplateInfoResponse[]
  templatesLoading: boolean
  templatesError: string | null
  selectedTemplate: string | null
  comparedTemplates: string[]
  templateVariables: Record<string, string | number | boolean>

  // Company
  companyName: string
  companyDescription: string
  currency: CurrencyCode
  budgetCapEnabled: boolean
  budgetCap: number | null
  companyResponse: SetupCompanyResponse | null
  companyLoading: boolean
  companyError: string | null

  // Agents
  agents: SetupAgentSummary[]
  agentsLoading: boolean
  agentsError: string | null

  // Providers
  providers: Record<string, ProviderConfig>
  presets: ProviderPreset[]
  presetsLoading: boolean
  presetsError: string | null
  probeResults: Record<string, ProbePresetResponse>
  probing: boolean
  providersLoading: boolean
  providersError: string | null

  // Theme
  themeSettings: ThemeSettings

  // Cost
  estimatedMonthlyCost: number | null

  // Completion
  completing: boolean
  completionError: string | null

  // Navigation actions
  setStep: (step: WizardStep) => void
  markStepComplete: (step: WizardStep) => void
  markStepIncomplete: (step: WizardStep) => void
  canNavigateTo: (step: WizardStep) => boolean
  setNeedsAdmin: (needsAdmin: boolean) => void
  setAccountCreated: (created: boolean) => void

  // Template actions
  fetchTemplates: () => Promise<void>
  selectTemplate: (name: string) => void
  toggleCompare: (name: string) => boolean
  clearComparison: () => void
  setTemplateVariable: (key: string, value: string | number | boolean) => void

  // Company actions
  setCompanyName: (name: string) => void
  setCompanyDescription: (desc: string) => void
  setCurrency: (currency: CurrencyCode) => void
  setBudgetCapEnabled: (enabled: boolean) => void
  setBudgetCap: (cap: number | null) => void
  submitCompany: () => Promise<void>

  // Agent actions
  fetchAgents: () => Promise<void>
  updateAgentModel: (index: number, provider: string, modelId: string) => Promise<void>
  updateAgentName: (index: number, name: string) => Promise<void>
  randomizeAgentName: (index: number) => Promise<void>

  // Provider actions
  fetchProviders: () => Promise<void>
  fetchPresets: () => Promise<void>
  createProviderFromPreset: (presetName: string, name: string, apiKey?: string) => Promise<void>
  testProviderConnection: (name: string) => Promise<TestConnectionResponse>
  probeAllPresets: () => Promise<void>

  // Theme actions
  setThemeSetting: <K extends keyof ThemeSettings>(key: K, value: ThemeSettings[K]) => void

  // Completion
  completeSetup: () => Promise<void>

  // Reset
  reset: () => void
}

const MAX_COMPARE = 3

function initialStepsCompleted(): Record<WizardStep, boolean> {
  return {
    account: false,
    template: false,
    company: false,
    agents: false,
    providers: false,
    theme: false,
    complete: false,
  }
}

function getInitialState() {
  return {
    currentStep: 'template' as WizardStep,
    stepOrder: STEP_ORDER_NO_ACCOUNT,
    stepsCompleted: initialStepsCompleted(),
    direction: 'forward' as const,
    needsAdmin: false,
    accountCreated: false,

    templates: [] as TemplateInfoResponse[],
    templatesLoading: false,
    templatesError: null as string | null,
    selectedTemplate: null as string | null,
    comparedTemplates: [] as string[],
    templateVariables: {} as Record<string, string | number | boolean>,

    companyName: '',
    companyDescription: '',
    currency: DEFAULT_CURRENCY,
    budgetCapEnabled: false,
    budgetCap: null as number | null,
    companyResponse: null as SetupCompanyResponse | null,
    companyLoading: false,
    companyError: null as string | null,

    agents: [] as SetupAgentSummary[],
    agentsLoading: false,
    agentsError: null as string | null,

    providers: {} as Record<string, ProviderConfig>,
    presets: [] as ProviderPreset[],
    presetsLoading: false,
    presetsError: null as string | null,
    probeResults: {} as Record<string, ProbePresetResponse>,
    probing: false,
    providersLoading: false,
    providersError: null as string | null,

    themeSettings: { ...DEFAULT_THEME },

    estimatedMonthlyCost: null as number | null,

    completing: false,
    completionError: null as string | null,
  }
}

export const useSetupWizardStore = create<SetupWizardState>()((set, get) => ({
  ...getInitialState(),

  // -- Navigation --

  setStep(step) {
    const { stepOrder, currentStep } = get()
    const currentIdx = stepOrder.indexOf(currentStep)
    const targetIdx = stepOrder.indexOf(step)
    set({
      currentStep: step,
      direction: targetIdx >= currentIdx ? 'forward' : 'backward',
    })
  },

  markStepComplete(step) {
    set((s) => ({
      stepsCompleted: { ...s.stepsCompleted, [step]: true },
    }))
  },

  markStepIncomplete(step) {
    set((s) => ({
      stepsCompleted: { ...s.stepsCompleted, [step]: false },
    }))
  },

  canNavigateTo(step) {
    const { stepOrder, stepsCompleted } = get()
    const targetIdx = stepOrder.indexOf(step)
    if (targetIdx === -1) return false
    if (targetIdx === 0) return true
    for (let i = 0; i < targetIdx; i++) {
      if (!stepsCompleted[stepOrder[i]!]) return false
    }
    return true
  },

  setNeedsAdmin(needsAdmin) {
    set({
      needsAdmin,
      stepOrder: needsAdmin ? FULL_STEP_ORDER : STEP_ORDER_NO_ACCOUNT,
      currentStep: needsAdmin ? 'account' : 'template',
    })
  },

  setAccountCreated(created) {
    set({ accountCreated: created })
  },

  // -- Template --

  async fetchTemplates() {
    set({ templatesLoading: true, templatesError: null })
    try {
      const templates = await listTemplates()
      set({ templates, templatesLoading: false })
    } catch (err) {
      console.error('setup-wizard: fetchTemplates failed:', err)
      set({ templatesError: getErrorMessage(err), templatesLoading: false })
    }
  },

  selectTemplate(name) {
    set({ selectedTemplate: name })
  },

  toggleCompare(name) {
    const { comparedTemplates } = get()
    if (comparedTemplates.includes(name)) {
      set({ comparedTemplates: comparedTemplates.filter((n) => n !== name) })
      return true
    }
    if (comparedTemplates.length >= MAX_COMPARE) return false
    set({ comparedTemplates: [...comparedTemplates, name] })
    return true
  },

  clearComparison() {
    set({ comparedTemplates: [] })
  },

  setTemplateVariable(key, value) {
    set((s) => ({
      templateVariables: { ...s.templateVariables, [key]: value },
    }))
  },

  // -- Company --

  setCompanyName(name) {
    set({ companyName: name })
  },

  setCompanyDescription(desc) {
    set({ companyDescription: desc })
  },

  setCurrency(currency) {
    set({ currency })
  },

  setBudgetCapEnabled(enabled) {
    set({ budgetCapEnabled: enabled })
  },

  setBudgetCap(cap) {
    set({ budgetCap: cap })
  },

  async submitCompany() {
    const { companyName, companyDescription, selectedTemplate } = get()
    set({ companyLoading: true, companyError: null })
    try {
      const response = await createCompany({
        company_name: companyName.trim(),
        description: companyDescription.trim() || null,
        template_name: selectedTemplate,
      })
      set({
        companyResponse: response,
        agents: [...response.agents],
        companyLoading: false,
      })
    } catch (err) {
      console.error('setup-wizard: submitCompany failed:', err)
      set({ companyError: getErrorMessage(err), companyLoading: false })
    }
  },

  // -- Agents --

  async fetchAgents() {
    set({ agentsLoading: true, agentsError: null })
    try {
      const agents = await getAgents()
      set({ agents: [...agents], agentsLoading: false })
    } catch (err) {
      console.error('setup-wizard: fetchAgents failed:', err)
      set({ agentsError: getErrorMessage(err), agentsLoading: false })
    }
  },

  async updateAgentModel(index, provider, modelId) {
    set({ agentsError: null })
    try {
      const updated = await apiUpdateAgentModel(index, {
        model_provider: provider,
        model_id: modelId,
      })
      set((s) => ({
        agents: s.agents.map((a, i) => i === index ? updated : a),
      }))
    } catch (err) {
      console.error('setup-wizard: updateAgentModel failed:', err)
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async updateAgentName(index, name) {
    set({ agentsError: null })
    try {
      const updated = await apiUpdateAgentName(index, { name })
      set((s) => ({
        agents: s.agents.map((a, i) => i === index ? updated : a),
      }))
    } catch (err) {
      console.error('setup-wizard: updateAgentName failed:', err)
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async randomizeAgentName(index) {
    set({ agentsError: null })
    try {
      const updated = await apiRandomizeAgentName(index)
      set((s) => ({
        agents: s.agents.map((a, i) => i === index ? updated : a),
      }))
    } catch (err) {
      console.error('setup-wizard: randomizeAgentName failed:', err)
      set({ agentsError: getErrorMessage(err) })
    }
  },

  // -- Providers --

  async fetchProviders() {
    set({ providersLoading: true, providersError: null })
    try {
      const providers = await listProviders()
      set({ providers, providersLoading: false })
    } catch (err) {
      console.error('setup-wizard: fetchProviders failed:', err)
      set({ providersError: getErrorMessage(err), providersLoading: false })
    }
  },

  async fetchPresets() {
    set({ presetsLoading: true, presetsError: null })
    try {
      const presets = await listPresets()
      set({ presets, presetsLoading: false })
    } catch (err) {
      console.error('setup-wizard: fetchPresets failed:', err)
      set({ presetsError: getErrorMessage(err), presetsLoading: false })
    }
  },

  async createProviderFromPreset(presetName, name, apiKey) {
    set({ providersError: null })
    try {
      const provider = await createFromPreset({
        preset_name: presetName,
        name,
        api_key: apiKey,
      })
      set((s) => ({
        providers: { ...s.providers, [name]: provider },
      }))
    } catch (err) {
      console.error('setup-wizard: createProviderFromPreset failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      throw err
    }
  },

  async testProviderConnection(name) {
    set({ providersError: null })
    try {
      return await testConnection(name)
    } catch (err) {
      console.error('setup-wizard: testProviderConnection failed:', err)
      set({ providersError: getErrorMessage(err) })
      throw err
    }
  },

  async probeAllPresets() {
    const { presets } = get()
    set({ probing: true })
    const entries = await Promise.allSettled(
      presets.map(async (preset) => {
        const result = await probePreset(preset.name)
        return [preset.name, result] as const
      }),
    )
    const results: Record<string, ProbePresetResponse> = {}
    for (const entry of entries) {
      if (entry.status === 'fulfilled') {
        results[entry.value[0]] = entry.value[1]
      } else {
        console.error('setup-wizard: probe failed for preset:', entry.reason)
      }
    }
    set({ probeResults: results, probing: false })
  },

  // -- Theme --

  setThemeSetting(key, value) {
    set((s) => ({
      themeSettings: { ...s.themeSettings, [key]: value },
    }))
  },

  // -- Completion --

  async completeSetup() {
    set({ completing: true, completionError: null })
    try {
      await completeSetup()
      set({ completing: false })
    } catch (err) {
      console.error('setup-wizard: completeSetup failed:', err)
      set({ completionError: getErrorMessage(err), completing: false })
      throw err
    }
  },

  // -- Reset --

  reset() {
    set(getInitialState())
  },
}))
