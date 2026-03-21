import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as settingsApi from '@/api/endpoints/settings'
import { getErrorMessage } from '@/utils/errors'
import {
  NAMESPACE_ORDER,
  SETTINGS_ADVANCED_KEY,
  SETTINGS_ADVANCED_WARNED_KEY,
} from '@/utils/constants'
import type { SettingDefinition, SettingEntry, SettingNamespace } from '@/api/types'

/** Backend max_length on UpdateSettingRequest.value. Also serves as ReDoS guard for regex validation. */
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

  // validator_pattern is sourced from the trusted backend SettingDefinition
  // schema, not end-user input. Mitigations: pattern length capped at 256 chars,
  // value length capped at MAX_SETTING_VALUE_LENGTH (8192).
  if (validator_pattern !== null) {
    if (validator_pattern.length > 256) {
      console.warn(
        `validator_pattern for ${definition.namespace}/${definition.key} exceeds 256 chars, skipping`,
      )
    } else {
      try {
        // Wrap server pattern in non-capturing group + anchors to prevent partial matches
        // and ensure the pattern cannot override the anchoring behavior
        if (!new RegExp(`^(?:${validator_pattern})$`).test(value)) { // eslint-disable-line security/detect-non-literal-regexp
          return `Must match pattern: ${validator_pattern}`
        }
      } catch (err) {
        console.warn(
          `Invalid validator_pattern for ${definition.namespace}/${definition.key}:`,
          validator_pattern, err,
        )
      }
    }
  }

  return null
}

/** Composite key format: `${namespace}/${key}`. */
type SettingCompositeKey = `${SettingNamespace}/${string}`

export interface DirtyField {
  namespace: SettingNamespace
  key: string
  value: string
}

export const useSettingsStore = defineStore('settings', () => {
  const schema = ref<SettingDefinition[]>([])
  const entries = ref<SettingEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const savingKey = ref<SettingCompositeKey | null>(null)
  let initialAdvanced = false
  try {
    initialAdvanced = localStorage.getItem(SETTINGS_ADVANCED_KEY) === 'true'
  } catch {
    // localStorage not available (restricted context) -- use default
  }
  const showAdvanced = ref(initialAdvanced)
  let generation = 0

  // ── Dirty tracking ──────────────────────────────────────────
  const dirtyFields = ref(new Map<SettingCompositeKey, DirtyField>())
  const hasDirty = computed(() => dirtyFields.value.size > 0)
  const dirtyCount = computed(() => dirtyFields.value.size)
  const savingAll = ref(false)

  function setDirty(namespace: SettingNamespace, key: string, value: string) {
    const next = new Map(dirtyFields.value)
    next.set(`${namespace}/${key}`, { namespace, key, value })
    dirtyFields.value = next
  }

  function clearDirty(namespace: SettingNamespace, key: string) {
    const next = new Map(dirtyFields.value)
    next.delete(`${namespace}/${key}`)
    dirtyFields.value = next
  }

  function clearAllDirty() {
    dirtyFields.value = new Map()
  }

  async function saveAllDirty(): Promise<{ saved: number; failed: number; errors: string[] }> {
    const fields = Array.from(dirtyFields.value.values())
    if (fields.length === 0) return { saved: 0, failed: 0, errors: [] }

    savingAll.value = true
    try {
      const results = await Promise.allSettled(
        fields.map((f) => updateSetting(f.namespace, f.key, f.value, { skipRefresh: true })),
      )
      let saved = 0
      let failed = 0
      const errors: string[] = []
      for (let i = 0; i < results.length; i++) {
        if (results[i].status === 'fulfilled') {
          saved++
          clearDirty(fields[i].namespace, fields[i].key)
        } else {
          failed++
          errors.push(getErrorMessage((results[i] as PromiseRejectedResult).reason))
        }
      }
      // Single refresh after all updates complete
      try {
        const gen = ++generation
        const entriesData = await settingsApi.getAllSettings()
        if (gen === generation) {
          entries.value = entriesData
        }
      } catch {
        // Best-effort -- individual optimistic updates already applied
      }
      return { saved, failed, errors }
    } finally {
      savingAll.value = false
    }
  }

  // ── Advanced toggle with warning ────────────────────────────
  /**
   * Attempt to toggle advanced mode.
   * Returns 'needs_warning' if the caller should show the confirmation dialog first.
   * Returns 'toggled' if the toggle was applied immediately (toggling OFF, or already warned).
   */
  function toggleAdvanced(): 'needs_warning' | 'toggled' {
    // Toggling OFF never needs a warning
    if (showAdvanced.value) {
      showAdvanced.value = false
      try { localStorage.setItem(SETTINGS_ADVANCED_KEY, 'false') } catch { /* noop */ }
      return 'toggled'
    }

    // Toggling ON -- check if we already warned this session
    let alreadyWarned = false
    try {
      alreadyWarned = sessionStorage.getItem(SETTINGS_ADVANCED_WARNED_KEY) === 'true'
    } catch { /* noop */ }

    if (alreadyWarned) {
      showAdvanced.value = true
      try { localStorage.setItem(SETTINGS_ADVANCED_KEY, 'true') } catch { /* noop */ }
      return 'toggled'
    }

    return 'needs_warning'
  }

  /** Called after the user confirms the advanced warning dialog. */
  function confirmAdvanced() {
    showAdvanced.value = true
    try {
      localStorage.setItem(SETTINGS_ADVANCED_KEY, 'true')
      sessionStorage.setItem(SETTINGS_ADVANCED_WARNED_KEY, 'true')
    } catch { /* noop */ }
  }

  // ── Namespaces ──────────────────────────────────────────────
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

  // ── Fetch ───────────────────────────────────────────────────
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

  // ── Update / Reset ─────────────────────────────────────────
  async function updateSetting(
    namespace: SettingNamespace,
    key: string,
    value: string,
    options?: { skipRefresh?: boolean },
  ): Promise<void> {
    savingKey.value = `${namespace}/${key}`
    try {
      const updatedEntry = await settingsApi.updateSetting(namespace, key, { value })
      // Immediately apply the returned entry so the UI reflects the change
      const idx = entries.value.findIndex(
        (e) => e.definition.namespace === namespace && e.definition.key === key,
      )
      if (idx >= 0) {
        entries.value = entries.value.map((e, i) => i === idx ? updatedEntry : e)
      } else {
        entries.value = [...entries.value, updatedEntry]
      }
      // Best-effort full refresh to get all resolved values
      // (skipped during batch saves -- saveAllDirty does a single refresh after)
      if (!options?.skipRefresh) {
        const gen = ++generation
        try {
          const entriesData = await settingsApi.getAllSettings()
          if (gen === generation) {
            entries.value = entriesData
          }
        } catch (refreshErr) {
          console.warn('Settings refresh failed after update:', refreshErr)
        }
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
    confirmAdvanced,
    // Dirty tracking
    dirtyFields,
    hasDirty,
    dirtyCount,
    savingAll,
    setDirty,
    clearDirty,
    clearAllDirty,
    saveAllDirty,
  }
})
