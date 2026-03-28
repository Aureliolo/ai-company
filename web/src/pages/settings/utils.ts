import type { SettingEntry, SettingNamespace } from '@/api/types'
import { SETTING_DEPENDENCIES } from '@/utils/constants'

/** Case-insensitive substring match across setting fields. */
export function matchesSetting(entry: SettingEntry, query: string): boolean {
  const q = query.toLowerCase()
  const def = entry.definition
  return (
    def.key.toLowerCase().includes(q) ||
    def.description.toLowerCase().includes(q) ||
    def.namespace.toLowerCase().includes(q) ||
    def.group.toLowerCase().includes(q)
  )
}

/** Check whether a controller setting is currently disabled (false/0). */
export function isControllerDisabled(
  controllerKey: string,
  entries: SettingEntry[],
  dirtyValues: ReadonlyMap<string, string>,
): boolean {
  const dirtyVal = dirtyValues.get(controllerKey)
  if (dirtyVal !== undefined) {
    return dirtyVal.toLowerCase() !== 'true' && dirtyVal !== '1'
  }
  const entry = entries.find(
    (e) => `${e.definition.namespace}/${e.definition.key}` === controllerKey,
  )
  if (!entry) return false
  return entry.value.toLowerCase() !== 'true' && entry.value !== '1'
}

/** Build a map of composite key -> whether its controller is disabled. */
export function buildControllerDisabledMap(
  entries: SettingEntry[],
  dirtyValues: ReadonlyMap<string, string>,
): Map<string, boolean> {
  const map = new Map<string, boolean>()
  for (const [controller, deps] of Object.entries(SETTING_DEPENDENCIES)) {
    const disabled = isControllerDisabled(controller, entries, dirtyValues)
    for (const dep of deps) {
      map.set(dep, disabled)
    }
  }
  return map
}

/** Save a batch of dirty settings via parallel PUTs. Returns the set of failed composite keys. */
export async function saveSettingsBatch(
  dirtyValues: ReadonlyMap<string, string>,
  updateSetting: (ns: SettingNamespace, key: string, value: string) => Promise<unknown>,
): Promise<Set<string>> {
  const keys = [...dirtyValues.keys()]
  const promises = keys.map((compositeKey) => {
    const [ns, key] = compositeKey.split('/') as [SettingNamespace, string]
    return updateSetting(ns, key, dirtyValues.get(compositeKey)!).then(() => undefined)
  })
  const results = await Promise.allSettled(promises)
  const failedKeys = new Set<string>()
  for (let i = 0; i < results.length; i++) {
    const result = results[i]
    const key = keys[i]
    if (result && key && result.status === 'rejected') {
      failedKeys.add(key)
    }
  }
  return failedKeys
}
