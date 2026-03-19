import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as settingsApi from '@/api/endpoints/settings'
import { getErrorMessage } from '@/utils/errors'
import { NAMESPACE_ORDER, SETTINGS_ADVANCED_KEY } from '@/utils/constants'
import type { SettingDefinition, SettingEntry, SettingNamespace } from '@/api/types'

/** Skip regex validation for inputs longer than this to mitigate ReDoS risk. */
const MAX_VALIDATION_INPUT_LENGTH = 10_000

/** Backend max_length on UpdateSettingRequest.value. */
const MAX_SETTING_VALUE_LENGTH = 8192

/**
 * Validate a value against a setting definition's constraints.
 * Returns null if valid, or an error message string if invalid.
 */
export function validateSettingValue(value: string, definition: SettingDefinition): string | null {
  if (value.length > MAX_SETTING_VALUE_LENGTH) {
    return `Value must be at most ${MAX_SETTING_VALUE_LENGTH} characters`
  }

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
    const lower = value.toLowerCase()
    if (lower !== 'true' && lower !== 'false' && lower !== '1' && lower !== '0') {
      return 'Must be true or false'
    }
  }

  if (type === 'enum') {
    if (!enum_values.includes(value)) return `Must be one of: ${enum_values.join(', ')}`
  }

  if (type === 'json') {
    try {
      const parsed = JSON.parse(value)
      if (typeof parsed !== 'object' || parsed === null) {
        return 'Must be a JSON object or array'
      }
    } catch {
      return 'Must be valid JSON'
    }
  }

  if (validator_pattern !== null) {
    if (value.length > MAX_VALIDATION_INPUT_LENGTH) return null
    try {
      if (!new RegExp(`^(?:${validator_pattern})$`).test(value)) {
        return `Must match pattern: ${validator_pattern}`
      }
    } catch (err) {
      console.warn(
        `Invalid validator_pattern for ${definition.namespace}/${definition.key}:`,
        validator_pattern, err,
      )
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
  let initialAdvanced = false
  try {
    initialAdvanced = localStorage.getItem(SETTINGS_ADVANCED_KEY) === 'true'
  } catch {
    // localStorage not available (restricted context) -- use default
  }
  const showAdvanced = ref(initialAdvanced)
  let generation = 0

  const namespaces = computed<SettingNamespace[]>(() => {
    const visible = schema.value.filter(
      (d) => showAdvanced.value || d.level !== 'advanced',
    )
    const present = new Set(visible.map((d) => d.namespace))
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

  async function updateSetting(namespace: SettingNamespace, key: string, value: string): Promise<void> {
    savingKey.value = `${namespace}/${key}`
    try {
      const updatedEntry = await settingsApi.updateSetting(namespace, key, { value })
      // Immediately apply the returned entry so the UI reflects the change
      const gen = ++generation
      entries.value = entries.value.map((e) =>
        e.definition.namespace === namespace && e.definition.key === key ? updatedEntry : e,
      )
      // Best-effort full refresh to get all resolved values
      try {
        const entriesData = await settingsApi.getAllSettings()
        if (gen === generation) {
          entries.value = entriesData
        }
      } catch (refreshErr) {
        console.warn('Settings refresh failed after update:', refreshErr)
      }
    } finally {
      savingKey.value = null
    }
  }

  async function resetSetting(namespace: SettingNamespace, key: string): Promise<void> {
    savingKey.value = `${namespace}/${key}`
    try {
      await settingsApi.resetSetting(namespace, key)
      // Optimistically revert entry to default since the DB override is deleted
      const gen = ++generation
      entries.value = entries.value.map((e) => {
        if (e.definition.namespace === namespace && e.definition.key === key) {
          return { ...e, value: e.definition.default ?? '', source: 'default' as const }
        }
        return e
      })
      // Best-effort full refresh to get actual resolved values (env/yaml may override default)
      try {
        const entriesData = await settingsApi.getAllSettings()
        if (gen === generation) {
          entries.value = entriesData
        }
      } catch (refreshErr) {
        console.warn('Settings refresh failed after reset:', refreshErr)
      }
    } finally {
      savingKey.value = null
    }
  }

  function toggleAdvanced(): void {
    showAdvanced.value = !showAdvanced.value
    try {
      localStorage.setItem(SETTINGS_ADVANCED_KEY, String(showAdvanced.value))
    } catch {
      // localStorage not available -- preference won't persist
    }
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
