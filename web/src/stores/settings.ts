import { create } from 'zustand'

import * as settingsApi from '@/api/endpoints/settings'

const CURRENCY_PATTERN = /^[A-Z]{3}$/

interface SettingsState {
  /** ISO 4217 currency code for display formatting. */
  currency: string
  /** Fetch the configured currency from the budget settings namespace. */
  fetchCurrency: () => Promise<void>
}

export const useSettingsStore = create<SettingsState>()((set) => ({
  currency: 'EUR',
  fetchCurrency: async () => {
    try {
      const entries = await settingsApi.getNamespaceSettings('budget')
      const currencyEntry = entries.find((e) => e.definition.key === 'currency')
      if (currencyEntry?.value && CURRENCY_PATTERN.test(currencyEntry.value)) {
        set({ currency: currencyEntry.value })
      }
    } catch {
      // Fall back to default EUR -- will retry on next fetch
    }
  },
}))
