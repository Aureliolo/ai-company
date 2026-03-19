import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as settingsApi from '@/api/endpoints/settings'
import { getErrorMessage } from '@/utils/errors'
import { NAMESPACE_ORDER, SETTINGS_ADVANCED_KEY } from '@/utils/constants'
import type { SettingDefinition, SettingEntry, SettingNamespace } from '@/api/types'

/**
 * Validate a value against a setting definition's constraints.
 * Returns null if valid, or an error message string if invalid.
 */
export function validateSettingValue(value: string, definition: SettingDefinition): string | null {
  const { type, min_value, max_value, enum_values, validator_pattern } = definition

  if (type === 'int') {
    if (value.trim() === '' || isNaN(Number(value))) return 'Must be a valid integer'
    const num = Number(value)
    if (!Number.isInteger(num)) return 'Must be a whole number'
    if (min_value !== null && num < min_value) return `Must be at least ${min_value}`
    if (max_value !== null && num > max_value) return `Must be at most ${max_value}`
  }

  if (type === 'float') {
    if (value.trim() === '' || isNaN(Number(value))) return 'Must be a valid number'
    const num = Number(value)
    if (!Number.isFinite(num)) return 'Must be a finite number'
    if (min_value !== null && num < min_value) return `Must be at least ${min_value}`
    if (max_value !== null && num > max_value) return `Must be at most ${max_value}`
  }

  if (type === 'bool') {
    if (value !== 'true' && value !== 'false') return 'Must be true or false'
  }

  if (type === 'enum') {
    if (!enum_values.includes(value)) return `Must be one of: ${enum_values.join(', ')}`
  }

  if (type === 'json') {
    try {
      JSON.parse(value)
    } catch {
      return 'Must be valid JSON'
    }
  }

  if (validator_pattern !== null) {
    try {
      if (!new RegExp(validator_pattern).test(value)) {
        return `Must match pattern: ${validator_pattern}`
      }
    } catch {
      // Invalid regex in definition -- skip client-side validation
    }
  }

  return null
}

export const useSettingsStore = defineStore('settings', () => {
  const schema = ref<SettingDefinition[]>([])
  const entries = ref<SettingEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const savingKey = ref<string | null>(null)
  const showAdvanced = ref(localStorage.getItem(SETTINGS_ADVANCED_KEY) === 'true')
  let generation = 0

  const namespaces = computed<SettingNamespace[]>(() => {
    const present = new Set(schema.value.map((d) => d.namespace))
    return NAMESPACE_ORDER.filter((ns) => present.has(ns))
  })

  function entriesByNamespace(ns: SettingNamespace): SettingEntry[] {
    return entries.value.filter((e) => e.definition.namespace === ns)
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    const gen = ++generation
    try {
      const [schemaData, entriesData] = await Promise.all([
        settingsApi.getSchema(),
        settingsApi.getAllSettings(),
      ])
      if (gen === generation) {
        schema.value = schemaData
        entries.value = entriesData
      }
    } catch (err) {
      if (gen === generation) {
        error.value = getErrorMessage(err)
      }
    } finally {
      if (gen === generation) {
        loading.value = false
      }
    }
  }

  async function updateSetting(namespace: string, key: string, value: string): Promise<void> {
    savingKey.value = `${namespace}/${key}`
    try {
      await settingsApi.updateSetting(namespace, key, { value })
      // Re-fetch all entries to get updated resolved values
      const gen = ++generation
      try {
        const entriesData = await settingsApi.getAllSettings()
        if (gen === generation) {
          entries.value = entriesData
        }
      } catch {
        // Refresh failed but the update itself succeeded -- non-fatal
      }
    } finally {
      savingKey.value = null
    }
  }

  async function resetSetting(namespace: string, key: string): Promise<void> {
    savingKey.value = `${namespace}/${key}`
    try {
      await settingsApi.resetSetting(namespace, key)
      // Re-fetch all entries to get updated resolved values
      const gen = ++generation
      try {
        const entriesData = await settingsApi.getAllSettings()
        if (gen === generation) {
          entries.value = entriesData
        }
      } catch {
        // Refresh failed but the reset itself succeeded -- non-fatal
      }
    } finally {
      savingKey.value = null
    }
  }

  function toggleAdvanced(): void {
    showAdvanced.value = !showAdvanced.value
    localStorage.setItem(SETTINGS_ADVANCED_KEY, String(showAdvanced.value))
  }

  return {
    schema,
    entries,
    loading,
    error,
    savingKey,
    showAdvanced,
    namespaces,
    entriesByNamespace,
    fetchAll,
    updateSetting,
    resetSetting,
    toggleAdvanced,
  }
})
