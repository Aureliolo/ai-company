/**
 * Structured condition expression types for the workflow editor.
 *
 * Supports simple comparisons that are compatible with the backend
 * condition evaluator (key == value, key != value).
 */

export type ComparisonOperator = '==' | '!='

export interface ConditionComparison {
  field: string
  operator: ComparisonOperator
  value: string
}

/**
 * Serialize a structured condition to the string format expected
 * by the backend condition evaluator.
 */
export function serializeCondition(condition: ConditionComparison): string {
  return `${condition.field} ${condition.operator} ${condition.value}`
}

/**
 * Parse a condition string back into a structured comparison.
 * Returns null if the string cannot be parsed.
 */
export function parseConditionString(str: string): ConditionComparison | null {
  const trimmed = str.trim()
  if (!trimmed) return null

  // Match patterns: "field == value" or "field != value"
  const match = trimmed.match(/^(\S+)\s+(==|!=)\s+(.+)$/)
  if (!match) return null

  return {
    field: match[1],
    operator: match[2] as ComparisonOperator,
    value: match[3].trim(),
  }
}

/** Common field suggestions for the condition builder. */
export const CONDITION_FIELDS = [
  'status',
  'priority',
  'task.status',
  'task.priority',
  'task.type',
  'approved',
  'env',
] as const

/** Common comparison values. */
export const CONDITION_VALUES = [
  'true',
  'false',
  'completed',
  'failed',
  'high',
  'medium',
  'low',
  'critical',
  'approved',
  'rejected',
] as const
