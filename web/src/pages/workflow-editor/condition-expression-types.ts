/**
 * Structured condition expression types for the workflow editor.
 *
 * Supports simple comparisons (key == value, key != value) and compound
 * expressions joined by AND/OR logical operators. Compatible with the
 * backend condition evaluator.
 */

export type ComparisonOperator = '==' | '!='

export type LogicalOperator = 'AND' | 'OR' | 'NOT'

export interface ConditionComparison {
  readonly kind: 'comparison'
  field: string
  operator: ComparisonOperator
  value: string
}

export interface ConditionGroup {
  readonly kind: 'group'
  logicalOperator: LogicalOperator
  conditions: ConditionExpression[]
}

export type ConditionExpression = ConditionComparison | ConditionGroup

/** Create a new comparison with default values. */
export function createComparison(
  field = 'status',
  operator: ComparisonOperator = '==',
  value = 'completed',
): ConditionComparison {
  return { kind: 'comparison', field, operator, value }
}

/** Create a new group with default values. */
export function createGroup(
  logicalOperator: LogicalOperator = 'AND',
  conditions: ConditionExpression[] = [],
): ConditionGroup {
  return { kind: 'group', logicalOperator, conditions }
}

/**
 * Serialize a structured condition expression to the string format
 * expected by the backend condition evaluator.
 *
 * Single comparison: "field == value"
 * Compound: "field1 == val1 AND field2 != val2"
 * Nested groups are wrapped in parentheses:
 *   "(field1 == val1 AND field2 != val2) OR field3 == val3"
 */
export function serializeCondition(expr: ConditionExpression): string {
  if (expr.kind === 'comparison') {
    return `${expr.field} ${expr.operator} ${expr.value}`
  }

  if (expr.conditions.length === 0) return ''

  // NOT wraps its single child in parentheses
  if (expr.logicalOperator === 'NOT') {
    const inner = expr.conditions.map((c) => serializeCondition(c)).join(' AND ')
    return `NOT (${inner})`
  }

  const parts = expr.conditions.map((c) => {
    // Nested groups get parenthesized to preserve precedence
    if (c.kind === 'group' && c.conditions.length > 1) {
      return `(${serializeCondition(c)})`
    }
    return serializeCondition(c)
  })

  return parts.join(` ${expr.logicalOperator} `)
}

/**
 * Parse a single comparison token: "field == value" or "field != value".
 * Returns null if the string cannot be parsed as a simple comparison.
 */
function parseSingleComparison(str: string): ConditionComparison | null {
  const trimmed = str.trim()
  if (!trimmed) return null

  const match = trimmed.match(/^(\S+)\s+(==|!=)\s+(.+)$/)
  if (!match) return null

  return createComparison(
    match[1]!,
    match[2] as ComparisonOperator,
    match[3]!.trim(),
  )
}

/**
 * Split a condition string by a logical operator, respecting parenthesized
 * groups. Returns null if the operator is not found at the top level.
 */
function splitByOperator(
  str: string,
  op: LogicalOperator,
): string[] | null {
  const parts: string[] = []
  let depth = 0
  let current = ''
  // Build a regex that matches the operator with flexible whitespace
  const tokenRegex = new RegExp(`\\s+${op}\\s+`) // eslint-disable-line security/detect-non-literal-regexp -- op is from LogicalOperator literal union
  let i = 0

  while (i < str.length) {
    if (str[i] === '(') {
      depth++
      current += '('
      i++
    } else if (str[i] === ')') {
      depth--
      if (depth < 0) return null // Unbalanced parens
      current += ')'
      i++
    } else if (depth === 0 && str.substring(i).match(tokenRegex)?.index === 0) {
      const match = str.substring(i).match(tokenRegex)!
      parts.push(current.trim())
      current = ''
      i += match[0].length
    } else {
      current += str[i]
      i++
    }
  }

  if (current.trim()) {
    parts.push(current.trim())
  }

  if (depth !== 0) return null // Unbalanced parens
  return parts.length > 1 ? parts : null
}

/**
 * Unwrap a single layer of balanced parentheses from a string.
 * "(foo == bar)" -> "foo == bar"
 * "(a == 1 AND b == 2)" -> "a == 1 AND b == 2"
 */
function unwrapParens(str: string): string {
  const trimmed = str.trim()
  if (!trimmed.startsWith('(') || !trimmed.endsWith(')')) return trimmed

  // Check if the outer parens are balanced as a pair
  let depth = 0
  for (let i = 0; i < trimmed.length - 1; i++) {
    if (trimmed[i] === '(') depth++
    else if (trimmed[i] === ')') depth--
    if (depth === 0) return trimmed // Inner close before end -- not a wrapping pair
  }

  return trimmed.slice(1, -1).trim()
}

/**
 * Parse a condition string into a structured expression.
 * Supports:
 * - Simple: "field == value"
 * - Compound: "field1 == val1 AND field2 != val2"
 * - Mixed: "field1 == val1 OR field2 != val2"
 * - Parenthesized groups: "(a == 1 AND b == 2) OR c == 3"
 *
 * Returns null if the string cannot be parsed.
 */
export function parseConditionString(str: string): ConditionExpression | null {
  const trimmed = str.trim()
  if (!trimmed) return null

  // Handle NOT prefix
  const notMatch = /^NOT\s*\((.+)\)\s*$/i.exec(trimmed)
  if (notMatch?.[1]) {
    const inner = parseConditionString(notMatch[1])
    if (!inner) return null
    // Preserve inner as a single child -- keep its operator intact
    return createGroup('NOT', [inner])
  }

  const unwrapped = unwrapParens(trimmed)

  // Split by OR first (lower precedence), then AND (higher precedence)
  for (const op of ['OR', 'AND'] as const) {
    const parts = splitByOperator(unwrapped, op)
    if (parts) {
      const conditions: ConditionExpression[] = []
      for (const part of parts) {
        const parsed = parseConditionString(part)
        if (!parsed) return null
        conditions.push(parsed)
      }
      return createGroup(op, conditions)
    }
  }

  // No logical operator found -- try single comparison
  return parseSingleComparison(unwrapped)
}

/**
 * Flatten a condition expression into a flat list of comparisons
 * plus the logical operator joining them. Returns null if the expression
 * contains nested groups (mixed AND/OR), which the flat builder cannot
 * represent.
 */
export function flattenExpression(
  expr: ConditionExpression,
): { comparisons: ConditionComparison[]; logicalOperator: LogicalOperator } | null {
  if (expr.kind === 'comparison') {
    return { comparisons: [expr], logicalOperator: 'AND' }
  }

  // Only flatten if all children are comparisons (no nested groups)
  const comparisons: ConditionComparison[] = []
  for (const child of expr.conditions) {
    if (child.kind !== 'comparison') return null
    comparisons.push(child)
  }

  return { comparisons, logicalOperator: expr.logicalOperator }
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
