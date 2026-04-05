import { useCallback, useMemo, useState } from 'react'
import { createLogger } from '@/lib/logger'
import type { SettingDefinition } from '@/api/types'
import { InputField } from '@/components/ui/input-field'
import { SelectField, type SelectOption } from '@/components/ui/select-field'
import { TagInput } from '@/components/ui/tag-input'
import { ToggleField } from '@/components/ui/toggle-field'
import { SIMPLE_ARRAY_SETTINGS } from '@/utils/constants'

const log = createLogger('settings')

export interface SettingFieldProps {
  definition: SettingDefinition
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

function parseArrayItems(value: string): string[] {
  if (!value.trim()) return []
  try {
    const parsed: unknown = JSON.parse(value)
    if (Array.isArray(parsed)) {
      return parsed.map(String)
    }
    log.warn('parseArrayItems: JSON value is not an array, displaying raw')
  } catch (err) {
    log.warn('parseArrayItems: not valid JSON, displaying raw value', err)
  }
  return [value]
}

/** Array setting rendered as tag/chip input. */
function ArraySettingField({
  value,
  onChange,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}) {
  const items = useMemo(() => parseArrayItems(value), [value])
  return (
    <TagInput
      value={items}
      onChange={(next) => onChange(JSON.stringify(next))}
      disabled={disabled}
      placeholder="Add item..."
    />
  )
}

export function SettingField({ definition, value, onChange, disabled }: SettingFieldProps) {
  const [validationError, setValidationError] = useState<string | null>(null)
  const compositeKey = `${definition.namespace}/${definition.key}`
  const isArraySetting = SIMPLE_ARRAY_SETTINGS.has(compositeKey)

  const validate = useCallback(
    (raw: string): string | null => {
      if (definition.type === 'int') {
        if (raw.trim() === '') return 'Required'
        const n = Number(raw)
        if (!Number.isInteger(n)) return 'Must be an integer'
        if (definition.min_value != null && n < definition.min_value)
          return `Minimum: ${definition.min_value}`
        if (definition.max_value != null && n > definition.max_value)
          return `Maximum: ${definition.max_value}`
      }
      if (definition.type === 'float') {
        if (raw.trim() === '') return 'Required'
        const n = Number(raw)
        if (Number.isNaN(n)) return 'Must be a number'
        if (definition.min_value != null && n < definition.min_value)
          return `Minimum: ${definition.min_value}`
        if (definition.max_value != null && n > definition.max_value)
          return `Maximum: ${definition.max_value}`
      }
      if (definition.validator_pattern) {
        try {
          // eslint-disable-next-line security/detect-non-literal-regexp -- pattern from trusted backend schema
          const re = new RegExp(definition.validator_pattern)
          if (!re.test(raw))
            return `Must match: ${definition.validator_pattern}`
        } catch (err) {
          log.warn(
            'Invalid validator_pattern for',
            `${definition.namespace}/${definition.key}:`,
            err,
          )
        }
      }
      return null
    },
    [definition],
  )

  // Derive input type before any early returns (hooks must be called unconditionally)
  const inputType = useMemo(() => {
    if (definition.type === 'int' || definition.type === 'float') return 'number'
    if (definition.sensitive) return 'password'
    return 'text'
  }, [definition.type, definition.sensitive])

  // Strip trailing ".0" / ".00" / ... from float values so the input shows
  // `10` instead of `10.0` when the backend serializes an integer-valued
  // float. Only the display changes -- the user's subsequent edits flow
  // straight through to the parent as-is, and the backend continues to
  // accept and store the value as a float.
  const displayValue = useMemo(() => {
    if (definition.type === 'float' && /^-?\d+\.0+$/.test(value)) {
      return value.replace(/\.0+$/, '')
    }
    return value
  }, [definition.type, value])

  if (definition.type === 'bool') {
    const checked = value.toLowerCase() === 'true' || value === '1'
    return (
      <ToggleField
        label=""
        checked={checked}
        onChange={(v) => onChange(v ? 'true' : 'false')}
        disabled={disabled}
      />
    )
  }

  if (definition.type === 'enum' && definition.enum_values.length > 0) {
    const options: SelectOption[] = definition.enum_values.map((v) => ({
      value: v,
      label: v,
    }))
    return (
      <SelectField
        label=""
        options={options}
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
    )
  }

  if (isArraySetting) {
    return (
      <ArraySettingField
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
    )
  }

  if (definition.type === 'json') {
    return (
      <InputField
        label=""
        multiline
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setValidationError(null)
        }}
        onBlur={() => {
          try {
            JSON.parse(value)
            setValidationError(null)
          } catch {
            setValidationError('Invalid JSON')
          }
        }}
        disabled={disabled}
        error={validationError}
      />
    )
  }

  return (
    <InputField
      label=""
      type={inputType}
      value={displayValue}
      onChange={(e) => {
        onChange(e.target.value)
        setValidationError(null)
      }}
      onBlur={() => {
        const err = validate(value)
        setValidationError(err)
      }}
      disabled={disabled}
      error={validationError}
    />
  )
}
