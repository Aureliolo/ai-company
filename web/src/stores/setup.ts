import { create } from 'zustand'
import { getSetupStatus } from '@/api/endpoints/setup'

interface SetupState {
  /** Whether initial setup is complete. `null` means not yet fetched. */
  setupComplete: boolean | null
  loading: boolean
  /** Whether the last fetch attempt failed. */
  error: boolean
  fetchSetupStatus: () => Promise<void>
}

// Dev-only: skip setup check when auth bypass is active
const DEV_SETUP_BYPASS = import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH_BYPASS === 'true'

export const useSetupStore = create<SetupState>()((set, get) => ({
  setupComplete: DEV_SETUP_BYPASS ? true : null,
  loading: false,
  error: false,

  async fetchSetupStatus() {
    if (get().loading) return
    set({ loading: true, error: false })
    try {
      const status = await getSetupStatus()
      set({ setupComplete: !status.needs_setup, loading: false })
    } catch {
      // On error (e.g. network failure), explicitly reset setupComplete
      // to null so the guard sees unknown state and shows error/retry
      set({ setupComplete: null, loading: false, error: true })
    }
  },
}))
