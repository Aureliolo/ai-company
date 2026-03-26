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
      if (!currencyEntry?.value) {
        console.warn('[settings] No currency value in budget settings, keeping default')
        return
      }
      if (!CURRENCY_PATTERN.test(currencyEntry.value)) {
        console.warn(`[settings] Invalid currency value: ${currencyEntry.value}, keeping default`)
        return
      }
      set({ currency: currencyEntry.value })
    } catch (error) {
      console.error('[settings] Failed to fetch currency setting:', error)
    }
  },
}))
