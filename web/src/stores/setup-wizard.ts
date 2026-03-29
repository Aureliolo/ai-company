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
  PersonalityPresetInfo,
} from '@/api/types'
import {
  listTemplates,
  createCompany,
  getAgents,
  updateAgentModel as apiUpdateAgentModel,
  updateAgentName as apiUpdateAgentName,
  randomizeAgentName as apiRandomizeAgentName,
  updateAgentPersonality as apiUpdateAgentPersonality,
  listPersonalityPresets,
  completeSetup,
} from '@/api/endpoints/setup'
import {
  listProviders,
  listPresets,
  createFromPreset,
  createProvider as apiCreateProvider,
  testConnection,
  probePreset,
  discoverModels,
  getProvider,
} from '@/api/endpoints/providers'
import type { CreateFromPresetRequest, CreateProviderRequest } from '@/api/types'
import { getErrorMessage } from '@/utils/errors'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import type { CurrencyCode } from '@/utils/currencies'

/** Probe all presets and collect results, logging failures. */
async function runProbeAll(
  presets: readonly ProviderPreset[],
  label: string,
): Promise<Record<string, ProbePresetResponse>> {
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
      console.error(
        `setup-wizard: ${label} failed:`,
        entry.reason,
      )
    }
  }
  return results
}

export type WizardStep =
  | 'account'
  | 'mode'
  | 'template'
  | 'company'
  | 'providers'
  | 'agents'
  | 'theme'
  | 'complete'

export type WizardMode = 'guided' | 'quick'

/** Guided mode: full step order with providers before agents. */
const GUIDED_STEP_ORDER: readonly WizardStep[] = [
  'mode', 'template', 'company',
  'providers', 'agents', 'theme', 'complete',
]

/** Quick mode: minimal steps (skip template, agents, theme). */
const QUICK_STEP_ORDER: readonly WizardStep[] = [
  'mode', 'company', 'providers', 'complete',
]

/** Guided mode with account creation first. */
const GUIDED_STEP_ORDER_WITH_ACCOUNT: readonly WizardStep[] = [
  'account', 'mode', 'template', 'company',
  'providers', 'agents', 'theme', 'complete',
]

/** Quick mode with account creation first. */
const QUICK_STEP_ORDER_WITH_ACCOUNT: readonly WizardStep[] = [
  'account', 'mode', 'company', 'providers', 'complete',
]

function getStepOrder(
  needsAdmin: boolean,
  mode: WizardMode,
): readonly WizardStep[] {
  if (needsAdmin) {
    return mode === 'guided'
      ? GUIDED_STEP_ORDER_WITH_ACCOUNT
      : QUICK_STEP_ORDER_WITH_ACCOUNT
  }
  return mode === 'guided'
    ? GUIDED_STEP_ORDER
    : QUICK_STEP_ORDER
}

export type ThemeSettings = {
  palette: 'warm-ops' | 'ice-station' | 'stealth' | 'signal' | 'neon'
  density: 'dense' | 'balanced' | 'sparse'
  animation: 'minimal' | 'status-driven' | 'spring' | 'instant'
  sidebar: 'rail' | 'collapsible' | 'hidden' | 'compact'
  typography: 'default'
}

const DEFAULT_THEME: ThemeSettings = {
  palette: 'warm-ops',
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
  wizardMode: WizardMode

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

  // Personality presets
  personalityPresets: PersonalityPresetInfo[]
  personalityPresetsLoading: boolean
  personalityPresetsError: string | null

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
  setWizardMode: (mode: WizardMode) => void

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
  updateAgentPersonality: (index: number, preset: string) => Promise<void>
  fetchPersonalityPresets: () => Promise<void>

  // Provider actions
  fetchProviders: () => Promise<void>
  fetchPresets: () => Promise<void>
  createProviderFromPreset: (presetName: string, name: string, apiKey?: string, baseUrl?: string) => Promise<void>
  createProviderFromPresetFull: (data: CreateFromPresetRequest) => Promise<ProviderConfig | null>
  createProviderCustom: (data: CreateProviderRequest) => Promise<ProviderConfig | null>
  testProviderConnection: (name: string) => Promise<TestConnectionResponse>
  probeAllPresets: () => Promise<void>
  reprobePresets: () => Promise<void>

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
    mode: false,
    template: false,
    company: false,
    providers: false,
    agents: false,
    theme: false,
    complete: false,
  }
}

function getInitialState() {
  return {
    currentStep: 'mode' as WizardStep,
    stepOrder: GUIDED_STEP_ORDER,
    stepsCompleted: initialStepsCompleted(),
    direction: 'forward' as const,
    needsAdmin: false,
    accountCreated: false,
    wizardMode: 'guided' as WizardMode,

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

    personalityPresets: [] as PersonalityPresetInfo[],
    personalityPresetsLoading: false,
    personalityPresetsError: null as string | null,

    providers: {} as Record<string, ProviderConfig>,
    presets: [] as ProviderPreset[],
    presetsLoading: false,
    presetsError: null as string | null,
    probeResults: {} as Record<string, ProbePresetResponse>,
    probing: false,
    providersLoading: false,
    providersError: null as string | null,

    themeSettings: { ...DEFAULT_THEME },

    completing: false,
    completionError: null as string | null,
  }
}

export const useSetupWizardStore = create<SetupWizardState>()((set, get) => ({
  ...getInitialState(),

  // -- Navigation --

  setStep(step) {
    const { stepOrder, currentStep } = get()
    const targetIdx = stepOrder.indexOf(step)
    if (targetIdx === -1) return // Step not in current flow (e.g. 'agents' in quick mode)
    const currentIdx = stepOrder.indexOf(currentStep)
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
    const { wizardMode } = get()
    const stepOrder = getStepOrder(needsAdmin, wizardMode)
    set({
      needsAdmin,
      stepOrder,
      currentStep: needsAdmin ? 'account' : 'mode',
    })
  },

  setAccountCreated(created) {
    set({ accountCreated: created })
  },

  setWizardMode(mode) {
    const { needsAdmin } = get()
    const stepOrder = getStepOrder(needsAdmin, mode)
    set((s) => {
      // Reset currentStep if it's not in the new order.
      const validStep = stepOrder.includes(s.currentStep)
        ? s.currentStep
        : stepOrder[0]
      return {
        wizardMode: mode,
        stepOrder,
        currentStep: validStep,
        // Clear template-derived state in quick mode to
        // prevent stale selectedTemplate from being sent.
        selectedTemplate: mode === 'quick'
          ? null : s.selectedTemplate,
        comparedTemplates: mode === 'quick'
          ? [] : s.comparedTemplates,
        templateVariables: mode === 'quick'
          ? {} : s.templateVariables,
        stepsCompleted: mode === 'quick'
          ? {
              ...s.stepsCompleted,
              template: false,
              agents: false,
              theme: false,
            }
          : s.stepsCompleted,
      }
    })
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

  async updateAgentPersonality(index, preset) {
    set({ agentsError: null })
    try {
      const updated = await apiUpdateAgentPersonality(index, { personality_preset: preset })
      set((s) => ({
        agents: s.agents.map((a, i) => i === index ? updated : a),
      }))
    } catch (err) {
      console.error('setup-wizard: updateAgentPersonality failed:', err)
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async fetchPersonalityPresets() {
    set({ personalityPresetsLoading: true, personalityPresetsError: null })
    try {
      const presets = await listPersonalityPresets()
      set({ personalityPresets: [...presets], personalityPresetsLoading: false })
    } catch (err) {
      console.error('setup-wizard: fetchPersonalityPresets failed:', err)
      set({ personalityPresetsError: getErrorMessage(err), personalityPresetsLoading: false })
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

  async createProviderFromPreset(presetName, name, apiKey, baseUrl) {
    set({ providersError: null })
    try {
      const provider = await createFromPreset({
        preset_name: presetName,
        name,
        api_key: apiKey,
        base_url: baseUrl,
      })
      set((s) => ({
        providers: { ...s.providers, [name]: provider },
      }))

      // Auto-discover models for local providers (auth_type=none).
      // The create endpoint may return 0 models if discovery was slow;
      // a post-creation discover call picks them up.
      if (provider.models.length === 0) {
        try {
          await discoverModels(name, presetName)
          // Re-fetch the provider to get the updated model list.
          const refreshed = await getProvider(name)
          set((s) => ({
            providers: { ...s.providers, [name]: refreshed },
          }))
          if (refreshed.models.length === 0) {
            set({
              providersError:
                `Provider '${name}' created but no ` +
                'models were discovered. Ensure the ' +
                'provider is running with models ' +
                'available, then refresh.',
            })
          }
        } catch (discoveryErr) {
          // Discovery is best-effort; provider was created but
          // user should know models could not be discovered.
          const msg = getErrorMessage(discoveryErr)
          console.error(
            'setup-wizard: model discovery failed for',
            name, msg,
          )
          set({
            providersError:
              `Provider '${name}' created but model` +
              ` discovery failed: ${msg}. ` +
              'Ensure the provider is running, ' +
              'then refresh the providers list.',
          })
        }
      }
    } catch (err) {
      console.error('setup-wizard: createProviderFromPreset failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      throw err
    }
  },

  async createProviderFromPresetFull(data) {
    set({ providersError: null })
    try {
      const provider = await createFromPreset(data)
      set((s) => ({
        providers: { ...s.providers, [data.name]: provider },
      }))

      // Auto-discover models for local providers (auth_type=none)
      if (provider.models.length === 0) {
        try {
          await discoverModels(data.name, data.preset_name)
          const refreshed = await getProvider(data.name)
          set((s) => ({
            providers: { ...s.providers, [data.name]: refreshed },
          }))
          if (refreshed.models.length === 0) {
            set({
              providersError:
                `Provider '${data.name}' created but no ` +
                'models were discovered. Ensure the ' +
                'provider is running with models ' +
                'available, then refresh.',
            })
          }
          return refreshed
        } catch (discoveryErr) {
          const msg = getErrorMessage(discoveryErr)
          console.error('setup-wizard: model discovery failed for', data.name, msg)
          set({
            providersError:
              `Provider '${data.name}' created but model ` +
              `discovery failed: ${msg}. ` +
              'Ensure the provider is running, then refresh.',
          })
        }
      }
      return provider
    } catch (err) {
      console.error('setup-wizard: createProviderFromPresetFull failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      return null
    }
  },

  async createProviderCustom(data) {
    set({ providersError: null })
    try {
      const provider = await apiCreateProvider(data)
      set((s) => ({
        providers: { ...s.providers, [data.name]: provider },
      }))
      return provider
    } catch (err) {
      console.error('setup-wizard: createProviderCustom failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      return null
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
    try {
      const results = await runProbeAll(presets, 'probe')
      set({ probeResults: results })
    } catch (err) {
      console.error('setup-wizard: probeAllPresets failed:', getErrorMessage(err))
    } finally {
      set({ probing: false })
    }
  },

  async reprobePresets() {
    set({ probeResults: {}, probing: true })
    try {
      const { presets } = get()
      const results = await runProbeAll(presets, 'reprobe')
      set({ probeResults: results })
    } catch (err) {
      console.error('setup-wizard: reprobePresets failed:', getErrorMessage(err))
    } finally {
      set({ probing: false })
    }
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
