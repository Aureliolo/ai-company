import { useCallback, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Brain,
  Eye,
  Globe,
  HardDrive,
  Network,
  Settings,
  Shield,
  Wallet,
  WifiOff,
} from 'lucide-react'
import type { SettingEntry, SettingNamespace } from '@/api/types'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ToggleField } from '@/components/ui/toggle-field'
import { useToastStore } from '@/stores/toast'
import { useSettingsStore } from '@/stores/settings'
import { useSettingsData } from '@/hooks/useSettingsData'
import {
  HIDDEN_SETTINGS,
  NAMESPACE_DISPLAY_NAMES,
  NAMESPACE_ORDER,
  SETTINGS_ADVANCED_KEY,
  SETTINGS_ADVANCED_WARNED_KEY,
} from '@/utils/constants'
import { AdvancedModeBanner } from './settings/AdvancedModeBanner'
import { CodeEditorPanel } from './settings/CodeEditorPanel'
import { FloatingSaveBar } from './settings/FloatingSaveBar'
import { NamespaceSection } from './settings/NamespaceSection'
import { SearchInput } from './settings/SearchInput'
import { SettingsSkeleton } from './settings/SettingsSkeleton'
import { buildControllerDisabledMap, matchesSetting, saveSettingsBatch } from './settings/utils'

type ViewMode = 'gui' | 'code'

const NAMESPACE_ICONS: Record<string, React.ReactNode> = {
  api: <Globe className="size-4" />,
  memory: <Brain className="size-4" />,
  budget: <Wallet className="size-4" />,
  security: <Shield className="size-4" />,
  coordination: <Network className="size-4" />,
  observability: <Eye className="size-4" />,
  backup: <HardDrive className="size-4" />,
}

export default function SettingsPage() {
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
  const [advancedMode, setAdvancedMode] = useState(
    () => localStorage.getItem(SETTINGS_ADVANCED_KEY) === 'true',
  )
  const [viewMode, setViewMode] = useState<ViewMode>('gui')
  const [dirtyValues, setDirtyValues] = useState<Map<string, string>>(() => new Map())
  const [showAdvancedWarning, setShowAdvancedWarning] = useState(false)

  // Filter entries: exclude hidden, filter by level, filter by search
  const filteredByNamespace = useMemo(() => {
    const result = new Map<SettingNamespace, SettingEntry[]>()
    for (const ns of NAMESPACE_ORDER) {
      const nsEntries = entries.filter((e) => {
        if (e.definition.namespace !== ns) return false
        const compositeKey = `${e.definition.namespace}/${e.definition.key}`
        if (HIDDEN_SETTINGS.has(compositeKey)) return false
        if (!advancedMode && e.definition.level === 'advanced') return false
        if (searchQuery && !matchesSetting(e, searchQuery)) return false
        return true
      })
      if (nsEntries.length > 0) {
        result.set(ns, nsEntries)
      }
    }
    return result
  }, [entries, advancedMode, searchQuery])

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

  const handleCodeSave = useCallback(
    async (changes: Map<string, string>): Promise<Set<string>> => {
      try {
        const failedKeys = await saveSettingsBatch(changes, updateSetting)

        // Reconcile GUI dirtyValues with code-mode saves
        setDirtyValues((prev) => {
          const next = new Map(prev)
          for (const [key, value] of changes) {
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
        return failedKeys
      } catch (err) {
        console.error('[settings] Unexpected error in handleCodeSave:', err)
        useToastStore.getState().add({ variant: 'error', title: 'Failed to save settings' })
        return new Set(changes.keys())
      }
    },
    [updateSetting],
  )

  const handleAdvancedToggle = useCallback((checked: boolean) => {
    if (checked) {
      const warned = sessionStorage.getItem(SETTINGS_ADVANCED_WARNED_KEY)
      if (warned !== 'true') {
        setShowAdvancedWarning(true)
        return
      }
    }
    setAdvancedMode(checked)
    localStorage.setItem(SETTINGS_ADVANCED_KEY, String(checked))
  }, [])

  const confirmAdvancedMode = useCallback(() => {
    sessionStorage.setItem(SETTINGS_ADVANCED_WARNED_KEY, 'true')
    setAdvancedMode(true)
    localStorage.setItem(SETTINGS_ADVANCED_KEY, 'true')
    setShowAdvancedWarning(false)
  }, [])

  if (loading && entries.length === 0) {
    return <SettingsSkeleton />
  }

  // Visible entries for code editor, overlaid with GUI drafts so Code mode sees unsaved GUI edits
  const codeEntries = entries
    .map((entry) => {
      const ck = `${entry.definition.namespace}/${entry.definition.key}`
      const dirtyValue = dirtyValues.get(ck)
      return dirtyValue !== undefined ? { ...entry, value: dirtyValue } : entry
    })
    .filter((e) => {
      const ck = `${e.definition.namespace}/${e.definition.key}`
      if (HIDDEN_SETTINGS.has(ck)) return false
      if (!advancedMode && e.definition.level === 'advanced') return false
      return NAMESPACE_ORDER.includes(e.definition.namespace)
    })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-lg font-semibold text-foreground">Settings</h1>
        <div className="flex items-center gap-4">
          <SearchInput value={searchQuery} onChange={setSearchQuery} className="w-64" />
          <ToggleField
            label="Code"
            checked={viewMode === 'code'}
            onChange={(v) => setViewMode(v ? 'code' : 'gui')}
          />
          <ToggleField
            label="Advanced"
            checked={advancedMode}
            onChange={handleAdvancedToggle}
          />
        </div>
      </div>

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

      {advancedMode && (
        <AdvancedModeBanner
          onDisable={() => {
            setAdvancedMode(false)
            localStorage.setItem(SETTINGS_ADVANCED_KEY, 'false')
          }}
        />
      )}

      {viewMode === 'code' ? (
        <ErrorBoundary level="section">
          <CodeEditorPanel entries={codeEntries} onSave={handleCodeSave} saving={saving} />
        </ErrorBoundary>
      ) : (
        <>
          {filteredByNamespace.size === 0 && (
            <EmptyState
              icon={Settings}
              title={searchQuery ? 'No matching settings' : 'No settings available'}
              description={
                searchQuery
                  ? 'Try a different search term or clear the filter.'
                  : 'Settings will appear once the backend is configured.'
              }
            />
          )}

          <StaggerGroup className="space-y-4">
            {NAMESPACE_ORDER.filter((ns) => filteredByNamespace.has(ns)).map((ns) => (
              <StaggerItem key={ns}>
                <ErrorBoundary level="section">
                  <NamespaceSection
                    displayName={NAMESPACE_DISPLAY_NAMES[ns]}
                    icon={NAMESPACE_ICONS[ns] ?? <Settings className="size-4" />}
                    entries={filteredByNamespace.get(ns)!}
                    dirtyValues={dirtyValues}
                    onValueChange={handleValueChange}
                    savingKeys={storeSavingKeys}
                    controllerDisabledMap={controllerDisabledMap}
                    forceOpen={searchQuery.length > 0}
                  />
                </ErrorBoundary>
              </StaggerItem>
            ))}
          </StaggerGroup>

          <FloatingSaveBar
            dirtyCount={dirtyValues.size}
            saving={saving}
            onSave={handleSave}
            onDiscard={handleDiscard}
            saveError={saveError}
          />
        </>
      )}

      <ConfirmDialog
        open={showAdvancedWarning}
        onOpenChange={setShowAdvancedWarning}
        title="Enable Advanced Mode?"
        description="Advanced settings control low-level system behavior. Misconfiguration may affect stability or security. Only change these if you know what you are doing."
        confirmLabel="Enable"
        onConfirm={confirmAdvancedMode}
      />
    </div>
  )
}
