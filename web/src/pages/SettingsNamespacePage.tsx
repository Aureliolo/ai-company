import { useCallback, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router'
import { AlertTriangle, ArrowLeft, Settings, WifiOff } from 'lucide-react'
import type { SettingEntry, SettingNamespace } from '@/api/types'
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
  SETTING_DEPENDENCIES,
  SETTINGS_ADVANCED_KEY,
} from '@/utils/constants'
import { ROUTES } from '@/router/routes'
import { FloatingSaveBar } from './settings/FloatingSaveBar'
import { NamespaceSection } from './settings/NamespaceSection'
import { SearchInput } from './settings/SearchInput'
import { SettingsSkeleton } from './settings/SettingsSkeleton'

function matchesSetting(entry: SettingEntry, query: string): boolean {
  const q = query.toLowerCase()
  const def = entry.definition
  return (
    def.key.toLowerCase().includes(q) ||
    def.description.toLowerCase().includes(q) ||
    def.group.toLowerCase().includes(q)
  )
}

function isControllerDisabled(
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

// Reuse NAMESPACE_ICONS from SettingsPage is not possible without extracting
// to a shared module, so we inline a simple icon for the namespace sub-page.

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

  const controllerDisabledMap = useMemo(() => {
    const map = new Map<string, boolean>()
    for (const [controller, deps] of Object.entries(SETTING_DEPENDENCIES)) {
      const disabled = isControllerDisabled(controller, entries, dirtyValues)
      for (const dep of deps) {
        map.set(dep, disabled)
      }
    }
    return map
  }, [entries, dirtyValues])

  const handleValueChange = useCallback((compositeKey: string, value: string) => {
    setDirtyValues((prev) => {
      const next = new Map(prev)
      next.set(compositeKey, value)
      return next
    })
  }, [])

  const handleDiscard = useCallback(() => {
    setDirtyValues(new Map())
  }, [])

  const handleSave = useCallback(async () => {
    const promises: Promise<void>[] = []
    for (const [compositeKey, value] of dirtyValues) {
      const [saveNs, key] = compositeKey.split('/') as [SettingNamespace, string]
      promises.push(updateSetting(saveNs, key, value).then(() => undefined))
    }
    const results = await Promise.allSettled(promises)
    const failures = results.filter((r) => r.status === 'rejected')
    if (failures.length === 0) {
      setDirtyValues(new Map())
      useToastStore.getState().add({ variant: 'success', title: 'Settings saved' })
    } else {
      useToastStore.getState().add({
        variant: 'error',
        title: `${failures.length} setting(s) failed to save`,
      })
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
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon">
            <Link to={ROUTES.SETTINGS}><ArrowLeft className="size-4" /></Link>
          </Button>
          <h1 className="text-lg font-semibold text-foreground">{displayName} Settings</h1>
        </div>
        <SearchInput value={searchQuery} onChange={setSearchQuery} className="w-64" />
      </div>

      {/* Banners */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      {/* Content */}
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
            namespace={ns}
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
