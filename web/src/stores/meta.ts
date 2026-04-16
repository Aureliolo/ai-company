import { create } from 'zustand'

import {
  getMetaConfig,
  getSignals,
  listABTests,
  listProposals,
  postChat,
  type ABTestSummary,
  type ChatResponse,
  type MetaConfig,
  type ProposalSummary,
  type SignalsResponse,
} from '@/api/endpoints/meta'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('meta')

interface MetaState {
  // Data
  config: MetaConfig | null
  proposals: readonly ProposalSummary[]
  abTests: readonly ABTestSummary[]
  signals: SignalsResponse | null

  // UI state
  loading: boolean
  error: string | null
  chatLoading: boolean

  // Actions
  fetchAll: () => Promise<void>
  fetchProposals: () => Promise<void>
  fetchSignals: () => Promise<void>
  sendChat: (question: string) => Promise<ChatResponse | null>
}

export const useMetaStore = create<MetaState>((set) => ({
  config: null,
  proposals: [],
  abTests: [],
  signals: null,
  loading: false,
  error: null,
  chatLoading: false,

  fetchAll: async () => {
    set({ loading: true, error: null })
    try {
      const [config, proposals, abTests, signals] = await Promise.all([
        getMetaConfig(),
        listProposals(),
        listABTests(),
        getSignals(),
      ])
      set({ config, proposals, abTests, signals, loading: false })
    } catch (err) {
      const msg = getErrorMessage(err)
      log.error('Failed to fetch meta data', msg)
      set({
        config: null,
        proposals: [],
        abTests: [],
        signals: null,
        error: msg,
        loading: false,
      })
    }
  },

  fetchProposals: async () => {
    set({ error: null })
    try {
      const proposals = await listProposals()
      set({ proposals })
    } catch (err) {
      const msg = getErrorMessage(err)
      log.error('Failed to fetch proposals', msg)
      set({ error: msg })
    }
  },

  fetchSignals: async () => {
    set({ error: null })
    try {
      const signals = await getSignals()
      set({ signals })
    } catch (err) {
      const msg = getErrorMessage(err)
      log.error('Failed to fetch signals', msg)
      set({ error: msg })
    }
  },

  sendChat: async (question: string) => {
    set({ chatLoading: true })
    try {
      const response = await postChat(question)
      return response
    } catch (err) {
      log.error('Chat request failed', getErrorMessage(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Chat request failed',
        description: getErrorMessage(err),
      })
      return null
    } finally {
      set({ chatLoading: false })
    }
  },
}))
