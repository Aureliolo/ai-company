import { create } from 'zustand'

import * as settingsApi from '@/api/endpoints/settings'

interface SettingsState {
  /** ISO 4217 currency code for display formatting. */
  currency: string
  /** Fetch the configured currency from the budget settings namespace. */
  fetchCurrency: () => Promise<void>
}

export const useSettingsStore = create<SettingsState>()((set) => ({
  currency: 'EUR',
  fetchCurrency: async () => {
    const entries = await settingsApi.getNamespaceSettings('budget')
    const currencyEntry = entries.find((e) => e.definition.key === 'currency')
    if (currencyEntry?.value) {
      set({ currency: currencyEntry.value })
    }
  },
}))
