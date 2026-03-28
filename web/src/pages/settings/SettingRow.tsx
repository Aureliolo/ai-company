import { cn } from '@/lib/utils'
import type { SettingEntry } from '@/api/types'
import {
  SETTING_DEPENDENCIES,
  SETTING_DEPENDED_BY,
  SECURITY_SENSITIVE_SETTINGS,
} from '@/utils/constants'
import { SourceBadge } from './SourceBadge'
import { RestartBadge } from './RestartBadge'
import { DependencyIndicator } from './DependencyIndicator'
import { SettingField } from './SettingField'

export interface SettingRowProps {
  entry: SettingEntry
  dirtyValue: string | undefined
  onChange: (value: string) => void
  saving: boolean
  /** Whether the controller setting for this dependent is disabled. */
  controllerDisabled?: boolean
}

function formatKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function SettingRow({
  entry,
  dirtyValue,
  onChange,
  saving,
  controllerDisabled,
}: SettingRowProps) {
  const { definition, source } = entry
  const compositeKey = `${definition.namespace}/${definition.key}`
  const displayValue = dirtyValue ?? entry.value
  const isEnvLocked = source === 'env'
  const isDisabled = isEnvLocked || saving || controllerDisabled === true
  const dependents = SETTING_DEPENDENCIES[compositeKey] ?? []
  const controller = SETTING_DEPENDED_BY[compositeKey]
  const isSecuritySensitive = SECURITY_SENSITIVE_SETTINGS.has(compositeKey)

  return (
    <div
      className={cn(
        'grid grid-cols-[1fr_auto] items-start gap-4 rounded-md px-3 py-3',
        'transition-colors hover:bg-card-hover',
        controllerDisabled && 'opacity-50',
      )}
    >
      {/* Left: label, description, badges */}
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {formatKey(definition.key)}
          </span>
          <SourceBadge source={source} />
          {definition.restart_required && <RestartBadge />}
          {dependents.length > 0 && (
            <DependencyIndicator dependents={dependents.map(formatDependentKey)} />
          )}
        </div>
        <p className="text-xs text-text-secondary">{definition.description}</p>
        {isEnvLocked && (
          <p className="text-[10px] text-warning">Value set by environment variable (read-only)</p>
        )}
        {controller && controllerDisabled && (
          <p className="text-[10px] text-text-muted">
            Requires {formatKey(controller.split('/')[1] ?? controller)} to be enabled
          </p>
        )}
        {isSecuritySensitive && (
          <p className="text-[10px] text-danger">
            Security-sensitive setting -- misconfiguration may expose the system
          </p>
        )}
      </div>

      {/* Right: field control */}
      <div className="w-56 shrink-0">
        <SettingField
          definition={definition}
          value={displayValue}
          onChange={onChange}
          disabled={isDisabled}
        />
      </div>
    </div>
  )
}

function formatDependentKey(compositeKey: string): string {
  const key = compositeKey.split('/')[1] ?? compositeKey
  return formatKey(key)
}
