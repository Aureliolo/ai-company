import { useCallback, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router'
import { AlertTriangle, ArrowLeft, Settings, WifiOff } from 'lucide-react'
import type { SettingNamespace } from '@/api/types'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useToastStore } from '@/stores/toast'
import { useSettingsStore } from '@/stores/settings'
import { useSettingsData } from '@/hooks/useSettingsData'
import {
  HIDDEN_SETTINGS,
  NAMESPACE_DISPLAY_NAMES,
  NAMESPACE_ORDER,
  SETTINGS_ADVANCED_KEY,
} from '@/utils/constants'
import { ROUTES } from '@/router/routes'
import { FloatingSaveBar } from './settings/FloatingSaveBar'
import { NamespaceSection } from './settings/NamespaceSection'
import { SearchInput } from './settings/SearchInput'
import { SettingsSkeleton } from './settings/SettingsSkeleton'
import { buildControllerDisabledMap, matchesSetting, saveSettingsBatch } from './settings/utils'

export default function SettingsNamespacePage() {
  const { namespace } = useParams<{ namespace: string }>()
  const {
    entries,
    loading,
    error,
    saving,
    saveError,
    wsConnected,
    wsSetupError,
    updateSetting,
  } = useSettingsData()

  const storeSavingKeys = useSettingsStore((s) => s.savingKeys)

  const [searchQuery, setSearchQuery] = useState('')
  const [dirtyValues, setDirtyValues] = useState<Map<string, string>>(() => new Map())
  const [advancedMode] = useState(() => localStorage.getItem(SETTINGS_ADVANCED_KEY) === 'true')
  const validNamespace = NAMESPACE_ORDER.includes(namespace as SettingNamespace)
  const ns = namespace as SettingNamespace

  const filteredEntries = useMemo(() => {
    if (!validNamespace) return []
    return entries.filter((e) => {
      if (e.definition.namespace !== ns) return false
      const compositeKey = `${e.definition.namespace}/${e.definition.key}`
      if (HIDDEN_SETTINGS.has(compositeKey)) return false
      if (!advancedMode && e.definition.level === 'advanced') return false
      if (searchQuery && !matchesSetting(e, searchQuery)) return false
      return true
    })
  }, [entries, ns, validNamespace, advancedMode, searchQuery])

  const controllerDisabledMap = useMemo(
    () => buildControllerDisabledMap(entries, dirtyValues),
    [entries, dirtyValues],
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

  const handleValueChange = useCallback((compositeKey: string, value: string) => {
    setDirtyValues((prev) => {
      const next = new Map(prev)
      if (persistedValues.get(compositeKey) === value) {
        next.delete(compositeKey)
      } else {
        next.set(compositeKey, value)
      }
      return next
    })
  }, [persistedValues])

  const handleDiscard = useCallback(() => {
    setDirtyValues(new Map())
  }, [])

  const handleSave = useCallback(async () => {
    try {
      const pending = new Map(dirtyValues)
      const failedKeys = await saveSettingsBatch(pending, updateSetting)

      setDirtyValues((prev) => {
        const next = new Map(prev)
        for (const [key, value] of pending) {
          if (!failedKeys.has(key) && next.get(key) === value) {
            next.delete(key)
          }
        }
        return next
      })

      if (failedKeys.size === 0) {
        useToastStore.getState().add({ variant: 'success', title: 'Settings saved' })
      } else {
        useToastStore.getState().add({
          variant: 'error',
          title: `${failedKeys.size} setting(s) failed to save`,
        })
      }
    } catch (err) {
      console.error('[settings] Unexpected error in handleSave:', err)
      useToastStore.getState().add({ variant: 'error', title: 'Failed to save settings' })
    }
  }, [dirtyValues, updateSetting])

  if (loading && entries.length === 0) {
    return <SettingsSkeleton />
  }

  if (!validNamespace) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon">
            <Link to={ROUTES.SETTINGS}><ArrowLeft className="size-4" /></Link>
          </Button>
          <h1 className="text-lg font-semibold text-foreground">Settings</h1>
        </div>
        <EmptyState
          icon={Settings}
          title="Unknown namespace"
          description={`"${namespace}" is not a valid settings namespace.`}
        />
      </div>
    )
  }

  const displayName = NAMESPACE_DISPLAY_NAMES[ns]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon">
            <Link to={ROUTES.SETTINGS}><ArrowLeft className="size-4" /></Link>
          </Button>
          <h1 className="text-lg font-semibold text-foreground">{displayName} Settings</h1>
        </div>
        <SearchInput value={searchQuery} onChange={setSearchQuery} className="w-64" />
      </div>

      {error && (
        <div className={cn(
          'flex items-center gap-2 rounded-lg',
          'border border-danger/30 bg-danger/5',
          'px-4 py-2 text-sm text-danger',
        )}>
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className={cn(
          'flex items-center gap-2 rounded-lg',
          'border border-warning/30 bg-warning/5',
          'px-4 py-2 text-sm text-warning',
        )}>
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      {filteredEntries.length === 0 ? (
        <EmptyState
          icon={Settings}
          title={searchQuery ? 'No matching settings' : 'No settings available'}
          description={
            searchQuery
              ? 'Try a different search term or clear the filter.'
              : `No ${displayName.toLowerCase()} settings are available.`
          }
        />
      ) : (
        <ErrorBoundary level="section">
          <NamespaceSection
            displayName={displayName}
            icon={<Settings className="size-4" />}
            entries={filteredEntries}
            dirtyValues={dirtyValues}
            onValueChange={handleValueChange}
            savingKeys={storeSavingKeys}
            controllerDisabledMap={controllerDisabledMap}
            forceOpen
          />
        </ErrorBoundary>
      )}

      <FloatingSaveBar
        dirtyCount={dirtyValues.size}
        saving={saving}
        onSave={handleSave}
        onDiscard={handleDiscard}
        saveError={saveError}
      />
    </div>
  )
}
