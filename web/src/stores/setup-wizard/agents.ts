import {
  getAgents,
  listPersonalityPresets,
  randomizeAgentName as apiRandomizeAgentName,
  updateAgentModel as apiUpdateAgentModel,
  updateAgentName as apiUpdateAgentName,
  updateAgentPersonality as apiUpdateAgentPersonality,
} from '@/api/endpoints/setup'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import type { AgentsSlice, SliceCreator } from './types'

const log = createLogger('setup-wizard:agents')

export const createAgentsSlice: SliceCreator<AgentsSlice> = (set) => ({
  agents: [],
  agentsLoading: false,
  agentsError: null,
  personalityPresets: [],
  personalityPresetsLoading: false,
  personalityPresetsError: null,

  async fetchAgents() {
    set({ agentsLoading: true, agentsError: null })
    try {
      const agents = await getAgents()
      set({ agents: [...agents], agentsLoading: false })
    } catch (err) {
      log.error('fetchAgents failed:', getErrorMessage(err))
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
      set((s) => ({ agents: s.agents.map((a, i) => (i === index ? updated : a)) }))
    } catch (err) {
      log.error('updateAgentModel failed:', getErrorMessage(err))
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async updateAgentName(index, name) {
    set({ agentsError: null })
    try {
      const updated = await apiUpdateAgentName(index, { name })
      set((s) => ({ agents: s.agents.map((a, i) => (i === index ? updated : a)) }))
    } catch (err) {
      log.error('updateAgentName failed:', getErrorMessage(err))
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async randomizeAgentName(index) {
    set({ agentsError: null })
    try {
      const updated = await apiRandomizeAgentName(index)
      set((s) => ({ agents: s.agents.map((a, i) => (i === index ? updated : a)) }))
    } catch (err) {
      log.error('randomizeAgentName failed:', getErrorMessage(err))
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async updateAgentPersonality(index, preset) {
    set({ agentsError: null })
    try {
      const updated = await apiUpdateAgentPersonality(index, { personality_preset: preset })
      set((s) => ({ agents: s.agents.map((a, i) => (i === index ? updated : a)) }))
    } catch (err) {
      log.error('updateAgentPersonality failed:', getErrorMessage(err))
      set({ agentsError: getErrorMessage(err) })
    }
  },

  async fetchPersonalityPresets() {
    set({ personalityPresetsLoading: true, personalityPresetsError: null })
    try {
      const presets = await listPersonalityPresets()
      set({ personalityPresets: [...presets], personalityPresetsLoading: false })
    } catch (err) {
      log.error('fetchPersonalityPresets failed:', getErrorMessage(err))
      set({
        personalityPresetsError: getErrorMessage(err),
        personalityPresetsLoading: false,
      })
    }
  },
})
