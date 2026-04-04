import { useCallback, useMemo, useRef, useState } from 'react'
import { createLogger } from '@/lib/logger'
import type { SettingEntry, SettingNamespace } from '@/api/types'
import { useToastStore } from '@/stores/toast'
import { saveSettingsBatch } from '@/pages/settings/utils'

const log = createLogger('useSettingsDirtyState')

export interface UseSettingsDirtyStateReturn {
  dirtyValues: Map<string, string>
  setDirtyValues: React.Dispatch<
    React.SetStateAction<Map<string, string>>
  >
  handleValueChange: (ck: string, value: string) => void
  handleDiscard: () => void
  handleSave: () => Promise<void>
  persistedValues: ReadonlyMap<string, string>
}

export function useSettingsDirtyState(
  entries: SettingEntry[],
  updateSetting: (
    ns: SettingNamespace,
    key: string,
    value: string,
  ) => Promise<unknown>,
): UseSettingsDirtyStateReturn {
  const [dirtyValues, setDirtyValues] = useState<Map<string, string>>(
    () => new Map(),
  )

  const persistedValues = useMemo(
    () =>
      new Map(
        entries.map((entry) => [
          `${entry.definition.namespace}/${entry.definition.key}`,
          entry.value,
        ]),
      ),
    [entries],
  )

  const handleValueChange = useCallback(
    (compositeKey: string, value: string) => {
      setDirtyValues((prev) => {
        const next = new Map(prev)
        if (persistedValues.get(compositeKey) === value) {
          next.delete(compositeKey)
        } else {
          next.set(compositeKey, value)
        }
        return next
      })
    },
    [persistedValues],
  )

  const handleDiscard = useCallback(() => {
    setDirtyValues(new Map())
  }, [])

  const isSavingRef = useRef(false)

  const handleSave = useCallback(async () => {
    if (isSavingRef.current) return
    isSavingRef.current = true
    try {
      const pending = new Map(dirtyValues)
      const failedKeys = await saveSettingsBatch(
        pending,
        updateSetting,
      )

      setDirtyValues((prev) => {
        const next = new Map(prev)
        for (const [key, value] of pending) {
          if (
            !failedKeys.has(key) &&
            next.get(key) === value
          ) {
            next.delete(key)
          }
        }
        return next
      })

      if (failedKeys.size === 0) {
        useToastStore.getState().add({
          variant: 'success',
          title: 'Settings saved',
        })
      } else {
        useToastStore.getState().add({
          variant: 'error',
          title: `${failedKeys.size} setting(s) failed to save`,
        })
      }
    } catch (err) {
      log.error(
        'Unexpected error in handleSave:',
        err,
      )
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to save settings',
      })
    } finally {
      isSavingRef.current = false
    }
  }, [dirtyValues, updateSetting])

  return {
    dirtyValues,
    setDirtyValues,
    handleValueChange,
    handleDiscard,
    handleSave,
    persistedValues,
  }
}
