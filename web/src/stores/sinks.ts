import { create } from 'zustand'
import type { SinkInfo, TestSinkResult } from '@/api/types'
import { listSinks, testSinkConfig } from '@/api/endpoints/settings'

interface SinksState {
  sinks: SinkInfo[]
  loading: boolean
  error: string | null
  fetchSinks: () => Promise<void>
  testConfig: (data: { sink_overrides: string; custom_sinks: string }) => Promise<TestSinkResult>
}

export const useSinksStore = create<SinksState>((set) => ({
  sinks: [],
  loading: false,
  error: null,

  fetchSinks: async () => {
    set({ loading: true, error: null })
    try {
      const sinks = await listSinks()
      set({ sinks, loading: false })
    } catch (err) {
      console.error('[sinks] fetchSinks failed:', err)
      const message = err instanceof Error ? err.message : 'Failed to load sinks'
      set({ error: message, loading: false })
    }
  },

  testConfig: async (data) => {
    return testSinkConfig(data)
  },
}))
