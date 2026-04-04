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
import { SelectField } from '@/components/ui/select-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { ToggleField } from '@/components/ui/toggle-field'
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

/** A sub-group containing its own operator and comparison rows. */
interface SubGroupEntry {
  key: number
  operator: 'AND' | 'OR'
  entries: ComparisonEntry[]
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

/** Build a ConditionExpression from the builder state (comparisons + sub-groups). */
function buildExpression(
  comparisons: ConditionComparison[],
  logicalOperator: LogicalOperator,
  subGroups: SubGroupEntry[] = [],
): ConditionExpression {
  const items: ConditionExpression[] = [...comparisons]
  for (const group of subGroups) {
    if (group.entries.length === 1) {
      items.push(group.entries[0]!.comparison)
    } else if (group.entries.length > 1) {
      items.push(createGroup(group.operator, group.entries.map((e) => e.comparison)))
    }
  }
  if (items.length === 1) return items[0]!
  return createGroup(logicalOperator, items)
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
        <SelectField
          label="Operator"
          options={OPERATORS}
          value={comparison.operator}
          onChange={(val) =>
            onUpdate(index, {
              ...comparison,
              operator: val as ComparisonOperator,
            })
          }
          className="h-8 w-24"
        />
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

  // Fix #41: Parse once during initialization and reuse the result.
  const initialFlat = useMemo(() => (value ? parseForBuilder(value) : null), []) // eslint-disable-line @eslint-react/exhaustive-deps -- intentionally mount-only

  const [mode, setMode] = useState<'builder' | 'advanced'>(() =>
    !value ? 'builder' : initialFlat ? 'builder' : 'advanced',
  )

  const [entries, setEntries] = useState<ComparisonEntry[]>(() => {
    if (initialFlat) return toEntries(initialFlat.comparisons)
    return toEntries([createComparison()])
  })

  const [logicalOperator, setLogicalOperator] = useState<LogicalOperator>(
    () => initialFlat?.logicalOperator ?? 'AND',
  )

  const [negate, setNegate] = useState(() => /^NOT\s*\(/i.test(value))
  const [subGroups, setSubGroups] = useState<SubGroupEntry[]>([])
  const [freeText, setFreeText] = useState(value)

  // Fix #12: Resync internal state when `value` changes externally.
  const lastSyncedRef = useRef(value)
  useEffect(() => {
    // Skip if the value matches what we last synced or what the builder
    // would currently serialize (avoids infinite loops from our own onChange).
    const currentComparisons = entries.map((e) => e.comparison)
    const currentSerialized =
      mode === 'builder'
        ? serializeCondition(buildExpression(currentComparisons, logicalOperator))
        : freeText

    if (value === lastSyncedRef.current || value === currentSerialized) {
      lastSyncedRef.current = value
      return
    }
    lastSyncedRef.current = value

    /* eslint-disable @eslint-react/set-state-in-effect -- legitimate prop-to-local-state sync */
    const flat = parseForBuilder(value)
    if (flat) {
      setEntries(toEntries(flat.comparisons))
      setLogicalOperator(flat.logicalOperator)
      setMode('builder')
    } else {
      setFreeText(value)
      setMode('advanced')
    }
    /* eslint-enable @eslint-react/set-state-in-effect */
  }, [value]) // eslint-disable-line @eslint-react/exhaustive-deps -- resync only when external value changes

  // Sync builder state -> parent
  const comparisons = useMemo(() => entries.map((e) => e.comparison), [entries])
  useEffect(() => {
    if (mode === 'builder') {
      const expr = buildExpression(comparisons, logicalOperator, subGroups)
      let serialized = serializeCondition(expr)
      if (negate && serialized) serialized = `NOT (${serialized})`
      if (serialized !== value) onChange(serialized)
    }
  }, [comparisons, logicalOperator, mode, value, negate, subGroups]) // eslint-disable-line @eslint-react/exhaustive-deps -- onChange is stable store callback

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

  const handleAddGroup = useCallback(() => {
    setSubGroups((prev) => [
      ...prev,
      {
        key: allocKey(),
        operator: 'AND' as const,
        entries: [{ key: allocKey(), comparison: createComparison() }],
      },
    ])
  }, [allocKey])

  const handleRemoveGroup = useCallback((groupKey: number) => {
    setSubGroups((prev) => prev.filter((g) => g.key !== groupKey))
  }, [])

  const handleGroupOperatorChange = useCallback((groupKey: number, op: 'AND' | 'OR') => {
    setSubGroups((prev) =>
      prev.map((g) => (g.key === groupKey ? { ...g, operator: op } : g)),
    )
  }, [])

  const handleGroupAddRow = useCallback(
    (groupKey: number) => {
      setSubGroups((prev) =>
        prev.map((g) =>
          g.key === groupKey
            ? { ...g, entries: [...g.entries, { key: allocKey(), comparison: createComparison() }] }
            : g,
        ),
      )
    },
    [allocKey],
  )

  const handleGroupUpdateRow = useCallback(
    (groupKey: number, index: number, updated: ConditionComparison) => {
      setSubGroups((prev) =>
        prev.map((g) =>
          g.key === groupKey
            ? {
                ...g,
                entries: g.entries.map((e, i) =>
                  i === index ? { ...e, comparison: updated } : e,
                ),
              }
            : g,
        ),
      )
    },
    [],
  )

  const handleGroupRemoveRow = useCallback((groupKey: number, index: number) => {
    setSubGroups((prev) =>
      prev.map((g) =>
        g.key === groupKey
          ? { ...g, entries: g.entries.filter((_, i) => i !== index) }
          : g,
      ).filter((g) => g.entries.length > 0),
    )
  }, [])

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
        const expr = buildExpression(comparisons, logicalOperator, subGroups)
        setFreeText(serializeCondition(expr))
      } else {
        // Fix #16: If the free text cannot be parsed, block the switch.
        const flat = parseForBuilder(freeText)
        if (!flat) return
        setEntries(toEntries(flat.comparisons))
        setLogicalOperator(flat.logicalOperator)
      }
      setMode(newMode)
    },
    [comparisons, logicalOperator, freeText, toEntries, subGroups],
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
          <ToggleField
            label="Negate (NOT)"
            description="Wrap the entire expression in NOT"
            checked={negate}
            onChange={setNegate}
          />
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
          {/* Sub-groups */}
          {subGroups.map((group) => (
            <div key={group.key} className="ml-4 space-y-2 rounded-md border border-border p-2">
              <div className="flex items-center justify-between">
                <SegmentedControl
                  label="Group operator"
                  value={group.operator}
                  onChange={(op) => handleGroupOperatorChange(group.key, op)}
                  options={[
                    { value: 'AND' as const, label: 'AND' },
                    { value: 'OR' as const, label: 'OR' },
                  ]}
                  size="sm"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveGroup(group.key)}
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-danger"
                  aria-label="Remove group"
                >
                  <X className="size-3.5" />
                </button>
              </div>
              {group.entries.map((entry, idx) => (
                <ComparisonRow
                  key={entry.key}
                  comparison={entry.comparison}
                  index={idx}
                  baseId={`${datalistId}-g${group.key}`}
                  canRemove={group.entries.length > 1}
                  onUpdate={(i, updated) => handleGroupUpdateRow(group.key, i, updated)}
                  onRemove={(i) => handleGroupRemoveRow(group.key, i)}
                />
              ))}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleGroupAddRow(group.key)}
              >
                <Plus data-icon="inline-start" className="size-3.5" />
                Add condition
              </Button>
            </div>
          ))}

          <div className="mt-1 flex gap-2">
            <Button variant="ghost" size="sm" onClick={handleAddRow}>
              <Plus data-icon="inline-start" className="size-3.5" />
              Add condition
            </Button>
            <Button variant="ghost" size="sm" onClick={handleAddGroup}>
              <Plus data-icon="inline-start" className="size-3.5" />
              Add group
            </Button>
          </div>
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
