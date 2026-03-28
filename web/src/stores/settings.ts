import { create } from 'zustand'

import * as settingsApi from '@/api/endpoints/settings'
import type { SettingDefinition, SettingEntry, SettingNamespace, WsEvent } from '@/api/types'
import { getErrorMessage } from '@/utils/errors'

const CURRENCY_PATTERN = /^[A-Z]{3}$/

interface SettingsState {
  /** ISO 4217 currency code for display formatting. */
  currency: string
  /** Full setting definitions (schema). */
  schema: SettingDefinition[]
  /** All setting entries with resolved values. */
  entries: SettingEntry[]
  /** Whether the initial fetch is in progress. */
  loading: boolean
  /** Error from the most recent fetch. */
  error: string | null
  /** Composite keys ("ns/key") currently being saved. */
  savingKeys: ReadonlySet<string>
  /** Error from the most recent save attempt. */
  saveError: string | null

  /** Fetch the configured currency from the budget settings namespace. */
  fetchCurrency: () => Promise<void>
  /** Fetch both schema and all settings entries. */
  fetchSettingsData: () => Promise<void>
  /** Lightweight re-fetch of entries only (for polling). */
  refreshEntries: () => Promise<void>
  /** Update a single setting value. Returns the updated entry on success. */
  updateSetting: (ns: SettingNamespace, key: string, value: string) => Promise<SettingEntry>
  /** Reset a setting to its default value. */
  resetSetting: (ns: SettingNamespace, key: string) => Promise<void>
  /** Handle a WebSocket event on the system channel. */
  updateFromWsEvent: (event: WsEvent) => void
}

export const useSettingsStore = create<SettingsState>()((set, get) => ({
  currency: 'EUR',
  schema: [],
  entries: [],
  loading: false,
  error: null,
  savingKeys: new Set(),
  saveError: null,

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
      console.warn(
        '[settings] Failed to fetch currency, keeping default:',
        getErrorMessage(error),
      )
    }
  },

  fetchSettingsData: async () => {
    set({ loading: true, error: null })
    try {
      const [schemaResult, entriesResult] = await Promise.allSettled([
        settingsApi.getSchema(),
        settingsApi.getAllSettings(),
      ])
      const schema = schemaResult.status === 'fulfilled' ? schemaResult.value : get().schema
      const entries = entriesResult.status === 'fulfilled' ? entriesResult.value : get().entries
      const errors: string[] = []
      if (schemaResult.status === 'rejected') {
        errors.push(`Schema: ${getErrorMessage(schemaResult.reason)}`)
      }
      if (entriesResult.status === 'rejected') {
        errors.push(`Settings: ${getErrorMessage(entriesResult.reason)}`)
      }
      set({
        schema,
        entries,
        loading: false,
        error: errors.length > 0 ? errors.join('; ') : null,
      })
    } catch (error) {
      set({ loading: false, error: getErrorMessage(error) })
    }
  },

  refreshEntries: async () => {
    // Let errors propagate to usePolling's error tracking
    const entries = await settingsApi.getAllSettings()
    set({ entries })
  },

  updateSetting: async (ns, key, value) => {
    const compositeKey = `${ns}/${key}`
    set((state) => ({
      savingKeys: new Set([...state.savingKeys, compositeKey]),
      saveError: null,
    }))
    try {
      const updated = await settingsApi.updateSetting(ns, key, { value })
      set((state) => {
        const newEntries = state.entries.map((e) =>
          e.definition.namespace === ns && e.definition.key === key ? updated : e,
        )
        const newSaving = new Set(state.savingKeys)
        newSaving.delete(compositeKey)
        return { entries: newEntries, savingKeys: newSaving }
      })
      return updated
    } catch (error) {
      set((state) => {
        const newSaving = new Set(state.savingKeys)
        newSaving.delete(compositeKey)
        return { savingKeys: newSaving, saveError: getErrorMessage(error) }
      })
      throw error
    }
  },

  resetSetting: async (ns, key) => {
    const compositeKey = `${ns}/${key}`
    set((state) => ({
      savingKeys: new Set([...state.savingKeys, compositeKey]),
      saveError: null,
    }))
    try {
      await settingsApi.resetSetting(ns, key)
    } catch (error) {
      set((state) => {
        const newSaving = new Set(state.savingKeys)
        newSaving.delete(compositeKey)
        return { savingKeys: newSaving, saveError: getErrorMessage(error) }
      })
      throw error
    }
    // Reset succeeded -- refetch entries to get the resolved default.
    let refreshedEntries: SettingEntry[] | undefined
    try {
      refreshedEntries = await settingsApi.getAllSettings()
    } catch (err) {
      // Reset applied but refetch failed -- UI is stale until next poll cycle
      console.warn('[settings] Post-reset refetch failed; data will refresh at next poll', err)
    } finally {
      set((state) => {
        const newSaving = new Set(state.savingKeys)
        newSaving.delete(compositeKey)
        const update: Partial<SettingsState> = { savingKeys: newSaving }
        if (refreshedEntries) update.entries = refreshedEntries
        return update
      })
    }
  },

  updateFromWsEvent: (event) => {
    if (event.channel === 'system') {
      void get().refreshEntries().catch((err) => {
        console.warn('[settings] WebSocket-triggered refresh failed:', getErrorMessage(err))
      })
    }
  },
}))
