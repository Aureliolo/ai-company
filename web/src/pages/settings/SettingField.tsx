import { useCallback, useMemo, useState } from 'react'
import type { SettingDefinition } from '@/api/types'
import { InputField } from '@/components/ui/input-field'
import { SelectField, type SelectOption } from '@/components/ui/select-field'
import { SliderField } from '@/components/ui/slider-field'
import { ToggleField } from '@/components/ui/toggle-field'
import { SIMPLE_ARRAY_SETTINGS } from '@/utils/constants'

export interface SettingFieldProps {
  definition: SettingDefinition
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

function parseArrayValue(value: string): string {
  try {
    const parsed: unknown = JSON.parse(value)
    if (Array.isArray(parsed)) {
      return parsed.join('\n')
    }
  } catch {
    // Not valid JSON, return as-is
  }
  return value
}

function serializeArrayValue(text: string): string {
  const items = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  return JSON.stringify(items)
}

export function SettingField({ definition, value, onChange, disabled }: SettingFieldProps) {
  const [validationError, setValidationError] = useState<string | null>(null)
  const compositeKey = `${definition.namespace}/${definition.key}`
  const isArraySetting = SIMPLE_ARRAY_SETTINGS.has(compositeKey)

  const validate = useCallback(
    (raw: string): string | null => {
      if (definition.type === 'int') {
        const n = Number(raw)
        if (!Number.isInteger(n)) return 'Must be an integer'
        if (definition.min_value != null && n < definition.min_value)
          return `Minimum: ${definition.min_value}`
        if (definition.max_value != null && n > definition.max_value)
          return `Maximum: ${definition.max_value}`
      }
      if (definition.type === 'float') {
        const n = Number(raw)
        if (Number.isNaN(n)) return 'Must be a number'
        if (definition.min_value != null && n < definition.min_value)
          return `Minimum: ${definition.min_value}`
        if (definition.max_value != null && n > definition.max_value)
          return `Maximum: ${definition.max_value}`
      }
      if (definition.validator_pattern) {
        try {
          if (!new RegExp(definition.validator_pattern).test(raw)) // eslint-disable-line security/detect-non-literal-regexp -- pattern from trusted backend schema
            return `Must match pattern: ${definition.validator_pattern}`
        } catch {
          // Invalid pattern -- skip client-side validation
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

  // Boolean toggle
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

  // Enum select
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

  // Numeric with range -- use slider when both bounds exist
  if (
    (definition.type === 'int' || definition.type === 'float') &&
    definition.min_value != null &&
    definition.max_value != null
  ) {
    const numValue = Number(value) || definition.min_value
    const step = definition.type === 'int' ? 1 : 0.1
    return (
      <SliderField
        label=""
        value={numValue}
        onChange={(v) => onChange(String(v))}
        min={definition.min_value}
        max={definition.max_value}
        step={step}
        disabled={disabled}
      />
    )
  }

  // Array settings -- multiline with one item per line
  if (isArraySetting) {
    const displayValue = parseArrayValue(value)
    return (
      <InputField
        label=""
        multiline
        value={displayValue}
        onChange={(e) => {
          onChange(serializeArrayValue(e.target.value))
          setValidationError(null)
        }}
        disabled={disabled}
        hint="One entry per line"
        error={validationError}
      />
    )
  }

  // JSON -- multiline textarea
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

  // Default: string/numeric input
  return (
    <InputField
      label=""
      type={inputType}
      value={value}
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
