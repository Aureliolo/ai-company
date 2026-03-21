import { computed, ref, type ComputedRef, type Ref } from 'vue'

export type EditMode = 'gui' | 'json' | 'yaml'

const STORAGE_KEY = 'settings_edit_mode'

function readPersistedMode(): EditMode {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (stored === 'json' || stored === 'yaml') return stored
  } catch {
    // sessionStorage not available
  }
  return 'gui'
}

export interface UseEditModeReturn {
  globalMode: Readonly<Ref<EditMode>>
  tabOverrides: Readonly<Ref<ReadonlyMap<string, EditMode>>>
  setGlobalMode: (mode: EditMode) => void
  setTabMode: (tab: string, mode: EditMode) => void
  clearTabMode: (tab: string) => void
  getEffectiveMode: (tab: string) => ComputedRef<EditMode>
}

// Module-level singleton state -- shared across all callers
const globalMode = ref<EditMode>(readPersistedMode())
const tabOverrides = ref<Map<string, EditMode>>(new Map())

/**
 * Composable for managing GUI/JSON/YAML edit mode state.
 * State is shared as a singleton across all pages.
 * Global mode persists to sessionStorage. Per-tab overrides are ephemeral.
 */
export function useEditMode(): UseEditModeReturn {
  function setGlobalMode(mode: EditMode) {
    globalMode.value = mode
    try {
      sessionStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // sessionStorage not available
    }
  }

  function setTabMode(tab: string, mode: EditMode) {
    const next = new Map(tabOverrides.value)
    next.set(tab, mode)
    tabOverrides.value = next
  }

  function clearTabMode(tab: string) {
    const next = new Map(tabOverrides.value)
    next.delete(tab)
    tabOverrides.value = next
  }

  function getEffectiveMode(tab: string): ComputedRef<EditMode> {
    return computed(() => tabOverrides.value.get(tab) ?? globalMode.value)
  }

  return {
    globalMode,
    tabOverrides,
    setGlobalMode,
    setTabMode,
    clearTabMode,
    getEffectiveMode,
  }
}
