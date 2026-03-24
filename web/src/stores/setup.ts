import { create } from 'zustand'
import { getSetupStatus } from '@/api/endpoints/setup'

interface SetupState {
  /** Whether initial setup is complete. `null` means not yet fetched. */
  setupComplete: boolean | null
  loading: boolean
  fetchSetupStatus: () => Promise<void>
}

export const useSetupStore = create<SetupState>()((set, get) => ({
  setupComplete: null,
  loading: false,

  async fetchSetupStatus() {
    if (get().loading) return
    set({ loading: true })
    try {
      const status = await getSetupStatus()
      set({ setupComplete: !status.needs_setup, loading: false })
    } catch {
      // On error (e.g. network failure), leave setupComplete as null
      // so the guard can retry on next navigation
      set({ loading: false })
    }
  },
}))
