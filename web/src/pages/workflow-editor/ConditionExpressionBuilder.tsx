/**
 * Structured condition expression builder for conditional workflow edges.
 *
 * Provides a Builder mode with multiple field/operator/value rows joined
 * by a configurable AND/OR logical operator, and an Advanced mode with
 * free-text input. The builder produces expressions compatible with the
 * backend condition evaluator.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SegmentedControl } from '@/components/ui/segmented-control'
import {
  CONDITION_FIELDS,
  CONDITION_VALUES,
  createComparison,
  createGroup,
  flattenExpression,
  parseConditionString,
  serializeCondition,
  type ComparisonOperator,
  type ConditionComparison,
  type ConditionExpression,
  type LogicalOperator,
} from './condition-expression-types'

/** A comparison row with a stable key for React list rendering. */
interface ComparisonEntry {
  key: number
  comparison: ConditionComparison
}

interface ConditionExpressionBuilderProps {
  value: string
  onChange: (value: string) => void
}

const OPERATORS: { value: ComparisonOperator; label: string }[] = [
  { value: '==', label: 'equals' },
  { value: '!=', label: 'not equals' },
]

/**
 * Try to parse a value string into a flat builder state (list of
 * comparisons + logical operator). Returns null if the expression
 * cannot be represented in the flat builder (e.g. nested groups).
 */
function parseForBuilder(
  str: string,
): { comparisons: ConditionComparison[]; logicalOperator: LogicalOperator } | null {
  const parsed = parseConditionString(str)
  if (!parsed) return null
  return flattenExpression(parsed)
}

/** Determine initial mode from the incoming value string. */
function getInitialMode(str: string): 'builder' | 'advanced' {
  if (!str) return 'builder'
  const flat = parseForBuilder(str)
  return flat ? 'builder' : 'advanced'
}

/** Build a ConditionExpression from the flat builder state. */
function buildExpression(
  comparisons: ConditionComparison[],
  logicalOperator: LogicalOperator,
): ConditionExpression {
  if (comparisons.length === 1) {
    return comparisons[0]!
  }
  return createGroup(logicalOperator, comparisons)
}

// ---- Sub-component: single comparison row ----

interface ComparisonRowProps {
  comparison: ConditionComparison
  index: number
  /** Unique base for datalist IDs to avoid collisions. */
  baseId: string
  canRemove: boolean
  onUpdate: (index: number, updated: ConditionComparison) => void
  onRemove: (index: number) => void
}

function ComparisonRow({
  comparison,
  index,
  baseId,
  canRemove,
  onUpdate,
  onRemove,
}: ComparisonRowProps) {
  const fieldsId = `${baseId}-fields-${index}`
  const valuesId = `${baseId}-values-${index}`

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Field</label>
        <input
          type="text"
          list={fieldsId}
          value={comparison.field}
          onChange={(e) =>
            onUpdate(index, { ...comparison, field: e.target.value })
          }
          className="h-8 w-32 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
          aria-label={`Condition field ${index + 1}`}
        />
        <datalist id={fieldsId}>
          {CONDITION_FIELDS.map((f) => (
            <option key={f} value={f} />
          ))}
        </datalist>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Operator</label>
        <select
          value={comparison.operator}
          onChange={(e) =>
            onUpdate(index, {
              ...comparison,
              operator: e.target.value as ComparisonOperator,
            })
          }
          className="h-8 w-24 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
          aria-label={`Comparison operator ${index + 1}`}
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
          list={valuesId}
          value={comparison.value}
          onChange={(e) =>
            onUpdate(index, { ...comparison, value: e.target.value })
          }
          className="h-8 w-32 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
          aria-label={`Condition value ${index + 1}`}
        />
        <datalist id={valuesId}>
          {CONDITION_VALUES.map((v) => (
            <option key={v} value={v} />
          ))}
        </datalist>
      </div>

      {canRemove && (
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => onRemove(index)}
          aria-label={`Remove condition ${index + 1}`}
        >
          <X className="size-3.5" />
        </Button>
      )}
    </div>
  )
}

// ---- Main builder ----

export function ConditionExpressionBuilder({
  value,
  onChange,
}: ConditionExpressionBuilderProps) {
  const datalistId = useId()
  const nextKeyRef = useRef(0)

  /** Allocate a monotonically increasing key for a new row. */
  const allocKey = useCallback(() => nextKeyRef.current++, [])

  /** Wrap comparisons into entries with stable keys. */
  const toEntries = useCallback(
    (comparisons: ConditionComparison[]): ComparisonEntry[] =>
      comparisons.map((comparison) => ({ key: allocKey(), comparison })),
    [allocKey],
  )

  const [mode, setMode] = useState<'builder' | 'advanced'>(() =>
    getInitialMode(value),
  )

  const [entries, setEntries] = useState<ComparisonEntry[]>(() => {
    const flat = parseForBuilder(value)
    if (flat) return toEntries(flat.comparisons)
    return toEntries([createComparison()])
  })

  const [logicalOperator, setLogicalOperator] = useState<LogicalOperator>(() => {
    const flat = parseForBuilder(value)
    return flat?.logicalOperator ?? 'AND'
  })

  const [freeText, setFreeText] = useState(value)

  // Sync builder state -> parent
  const comparisons = useMemo(() => entries.map((e) => e.comparison), [entries])
  useEffect(() => {
    if (mode === 'builder') {
      const expr = buildExpression(comparisons, logicalOperator)
      const serialized = serializeCondition(expr)
      if (serialized !== value) onChange(serialized)
    }
  }, [comparisons, logicalOperator, mode]) // eslint-disable-line @eslint-react/exhaustive-deps -- onChange is stable store callback

  const handleUpdateRow = useCallback(
    (index: number, updated: ConditionComparison) => {
      setEntries((prev) =>
        prev.map((entry, i) =>
          i === index ? { ...entry, comparison: updated } : entry,
        ),
      )
    },
    [],
  )

  const handleRemoveRow = useCallback((index: number) => {
    setEntries((prev) => {
      if (prev.length <= 1) return prev
      return prev.filter((_, i) => i !== index)
    })
  }, [])

  const handleAddRow = useCallback(() => {
    setEntries((prev) => [
      ...prev,
      { key: allocKey(), comparison: createComparison() },
    ])
  }, [allocKey])

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
        const expr = buildExpression(comparisons, logicalOperator)
        setFreeText(serializeCondition(expr))
      } else {
        const flat = parseForBuilder(freeText)
        if (flat) {
          setEntries(toEntries(flat.comparisons))
          setLogicalOperator(flat.logicalOperator)
        }
      }
      setMode(newMode)
    },
    [comparisons, logicalOperator, freeText, toEntries],
  )

  return (
    <div className="space-y-3">
      <SegmentedControl
        label="Condition mode"
        value={mode}
        onChange={handleModeChange}
        options={[
          { value: 'builder' as const, label: 'Builder' },
          { value: 'advanced' as const, label: 'Advanced' },
        ]}
        size="sm"
      />

      {mode === 'builder' ? (
        <div className="space-y-2">
          {entries.map((entry, index) => (
            <div key={entry.key} className="flex flex-col gap-2">
              {index > 0 && (
                <div className="flex items-center gap-2 pl-1">
                  <SegmentedControl
                    label="Logical operator"
                    value={logicalOperator}
                    onChange={setLogicalOperator}
                    options={[
                      { value: 'AND' as const, label: 'AND' },
                      { value: 'OR' as const, label: 'OR' },
                    ]}
                    size="sm"
                  />
                </div>
              )}
              <ComparisonRow
                comparison={entry.comparison}
                index={index}
                baseId={datalistId}
                canRemove={entries.length > 1}
                onUpdate={handleUpdateRow}
                onRemove={handleRemoveRow}
              />
            </div>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleAddRow}
            className="mt-1"
          >
            <Plus data-icon="inline-start" className="size-3.5" />
            Add condition
          </Button>
        </div>
      ) : (
        <input
          type="text"
          value={freeText}
          onChange={(e) => handleFreeTextChange(e.target.value)}
          placeholder="e.g. status == completed AND priority != low"
          className="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground"
          aria-label="Condition expression"
        />
      )}
    </div>
  )
}
