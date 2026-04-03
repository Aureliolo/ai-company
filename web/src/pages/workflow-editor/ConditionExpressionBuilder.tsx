/**
 * Structured condition expression builder for conditional workflow edges.
 *
 * Provides a Builder mode with field/operator/value selectors and an
 * Advanced mode with free-text input. The builder produces expressions
 * compatible with the backend condition evaluator.
 */

import { useCallback, useEffect, useState } from 'react'
import { SegmentedControl } from '@/components/ui/segmented-control'
import {
  CONDITION_FIELDS,
  CONDITION_VALUES,
  parseConditionString,
  serializeCondition,
  type ComparisonOperator,
  type ConditionComparison,
} from './condition-expression-types'

interface ConditionExpressionBuilderProps {
  value: string
  onChange: (value: string) => void
}

const OPERATORS: { value: ComparisonOperator; label: string }[] = [
  { value: '==', label: 'equals' },
  { value: '!=', label: 'not equals' },
]

const EMPTY_CONDITION: ConditionComparison = {
  field: 'status',
  operator: '==',
  value: 'completed',
}

export function ConditionExpressionBuilder({
  value,
  onChange,
}: ConditionExpressionBuilderProps) {
  const [mode, setMode] = useState<'builder' | 'advanced'>(() => {
    const parsed = parseConditionString(value)
    return parsed ? 'builder' : value ? 'advanced' : 'builder'
  })

  const [condition, setCondition] = useState<ConditionComparison>(() => {
    return parseConditionString(value) ?? EMPTY_CONDITION
  })

  const [freeText, setFreeText] = useState(value)

  // Sync builder -> parent
  useEffect(() => {
    if (mode === 'builder') {
      const serialized = serializeCondition(condition)
      if (serialized !== value) onChange(serialized)
    }
  }, [condition, mode]) // eslint-disable-line @eslint-react/exhaustive-deps -- onChange is stable store callback

  const handleFieldChange = useCallback(
    (field: string) => {
      setCondition((prev) => ({ ...prev, field }))
    },
    [],
  )

  const handleOperatorChange = useCallback(
    (operator: ComparisonOperator) => {
      setCondition((prev) => ({ ...prev, operator }))
    },
    [],
  )

  const handleValueChange = useCallback(
    (val: string) => {
      setCondition((prev) => ({ ...prev, value: val }))
    },
    [],
  )

  const handleFreeTextChange = useCallback(
    (text: string) => {
      setFreeText(text)
      onChange(text)
    },
    [onChange],
  )

  const handleModeChange = useCallback(
    (newMode: 'builder' | 'advanced') => {
      if (newMode === 'advanced') {
        setFreeText(serializeCondition(condition))
      } else {
        const parsed = parseConditionString(freeText)
        if (parsed) setCondition(parsed)
      }
      setMode(newMode)
    },
    [condition, freeText],
  )

  return (
    <div className="space-y-3">
      <SegmentedControl
        value={mode}
        onChange={handleModeChange}
        options={[
          { value: 'builder' as const, label: 'Builder' },
          { value: 'advanced' as const, label: 'Advanced' },
        ]}
        size="sm"
      />

      {mode === 'builder' ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Field</label>
            <input
              type="text"
              list="condition-fields"
              value={condition.field}
              onChange={(e) => handleFieldChange(e.target.value)}
              className="h-8 w-32 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
              aria-label="Condition field"
            />
            <datalist id="condition-fields">
              {CONDITION_FIELDS.map((f) => (
                <option key={f} value={f} />
              ))}
            </datalist>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Operator</label>
            <select
              value={condition.operator}
              onChange={(e) => handleOperatorChange(e.target.value as ComparisonOperator)}
              className="h-8 w-24 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
              aria-label="Comparison operator"
            >
              {OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Value</label>
            <input
              type="text"
              list="condition-values"
              value={condition.value}
              onChange={(e) => handleValueChange(e.target.value)}
              className="h-8 w-32 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
              aria-label="Condition value"
            />
            <datalist id="condition-values">
              {CONDITION_VALUES.map((v) => (
                <option key={v} value={v} />
              ))}
            </datalist>
          </div>
        </div>
      ) : (
        <input
          type="text"
          value={freeText}
          onChange={(e) => handleFreeTextChange(e.target.value)}
          placeholder="e.g. status == completed"
          className="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground"
          aria-label="Condition expression"
        />
      )}
    </div>
  )
}
