import { useCallback, useMemo, useRef, useState } from 'react'
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
  } catch (err) {
    console.warn('[settings] parseArrayValue: not valid JSON, displaying raw value', err)
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

/** Array setting with local draft to avoid serialization on every keystroke. */
function ArraySettingField({
  value,
  onChange,
  disabled,
  validationError,
  setValidationError,
}: {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  validationError: string | null
  setValidationError: (err: string | null) => void
}) {
  const [draft, setDraft] = useState(() => parseArrayValue(value))
  const prevValueRef = useRef(value)
  if (value !== prevValueRef.current) {
    prevValueRef.current = value
    setDraft(parseArrayValue(value))
  }
  return (
    <InputField
      label=""
      multiline
      value={draft}
      onChange={(e) => {
        setDraft(e.target.value)
        setValidationError(null)
      }}
      onBlur={() => onChange(serializeArrayValue(draft))}
      disabled={disabled}
      hint="One entry per line"
      error={validationError}
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
          console.warn(
            '[settings] Invalid validator_pattern for',
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

  // Numeric with range -- use slider when both bounds exist
  if (
    (definition.type === 'int' || definition.type === 'float') &&
    definition.min_value != null &&
    definition.max_value != null
  ) {
    const parsedValue = Number(value)
    const numValue = Number.isNaN(parsedValue) ? definition.min_value : parsedValue
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

  if (isArraySetting) {
    return (
      <ArraySettingField
        value={value}
        onChange={onChange}
        disabled={disabled}
        validationError={validationError}
        setValidationError={setValidationError}
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
