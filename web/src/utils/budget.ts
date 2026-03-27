/** Budget page utility functions -- pure computations with no side effects. */

import { computeSpendTrend } from '@/utils/dashboard'
import { formatCurrency } from '@/utils/format'
import type {
  ActivityItem,
  BudgetAlertConfig,
  BudgetConfig,
  CostRecord,
  ForecastResponse,
  OverviewMetrics,
  TrendDataPoint,
} from '@/api/types'

// ── Types ──────────────────────────────────────────────────

export type AggregationPeriod = 'hourly' | 'daily' | 'weekly'
export type BreakdownDimension = 'agent' | 'department' | 'provider'
export type ThresholdZone = 'normal' | 'amber' | 'red' | 'critical'

export interface AgentSpendingRow {
  agentId: string
  agentName: string
  totalCost: number
  budgetPercent: number
  taskCount: number
  costPerTask: number
}

export interface BreakdownSlice {
  key: string
  label: string
  cost: number
  percent: number
  color: string
}

export interface CategoryRatio {
  productive: { cost: number; percent: number; count: number }
  coordination: { cost: number; percent: number; count: number }
  system: { cost: number; percent: number; count: number }
  uncategorized: { cost: number; percent: number; count: number }
}

/** MetricCard data shape matching the MetricCard component props. */
export interface BudgetMetricCardData {
  label: string
  value: string | number
  change?: { value: number; direction: 'up' | 'down' }
  sparklineData?: number[]
  progress?: { current: number; total: number }
  subText?: string
}

// ── Constants ──────────────────────────────────────────────

/** Color palette for donut chart slices using CSS custom properties. */
export const DONUT_COLORS: readonly string[] = [
  'var(--so-accent)',
  'var(--so-success)',
  'var(--so-warning)',
  'var(--so-danger)',
  'var(--so-text-secondary)',
  'var(--so-text-muted)',
]

/** Budget-related WsEventType values used for filtering CFO events. */
const CFO_EVENT_TYPES = new Set(['budget.record_added', 'budget.alert'])

// ── Functions ──────────────────────────────────────────────

/**
 * Group cost records by agent and compute spending metrics.
 *
 * Returns rows sorted by totalCost descending. Agent display names are
 * looked up from `agentNameMap`, falling back to the raw agent_id.
 */
export function computeAgentSpending(
  records: readonly CostRecord[],
  budgetTotal: number,
  agentNameMap: ReadonlyMap<string, string>,
): AgentSpendingRow[] {
  if (records.length === 0) return []

  const groups = new Map<string, { cost: number; tasks: Set<string> }>()
  for (const r of records) {
    let group = groups.get(r.agent_id)
    if (!group) {
      group = { cost: 0, tasks: new Set() }
      groups.set(r.agent_id, group)
    }
    group.cost += r.cost_usd
    group.tasks.add(r.task_id)
  }

  const rows: AgentSpendingRow[] = []
  for (const [agentId, group] of groups) {
    const taskCount = group.tasks.size
    rows.push({
      agentId,
      agentName: agentNameMap.get(agentId) ?? agentId,
      totalCost: group.cost,
      budgetPercent: budgetTotal > 0 ? (group.cost / budgetTotal) * 100 : 0,
      taskCount,
      costPerTask: taskCount > 0 ? group.cost / taskCount : 0,
    })
  }

  return rows.sort((a, b) => b.totalCost - a.totalCost)
}

/**
 * Group cost records by the given dimension and compute breakdown slices.
 *
 * For the `'department'` dimension, agent IDs are mapped to departments
 * via `agentDeptMap`. Unmapped agents are grouped under "Unknown".
 */
export function computeCostBreakdown(
  records: readonly CostRecord[],
  dimension: BreakdownDimension,
  agentNameMap: ReadonlyMap<string, string>,
  agentDeptMap: ReadonlyMap<string, string>,
): BreakdownSlice[] {
  if (records.length === 0) return []

  const groups = new Map<string, number>()
  let totalCost = 0

  for (const r of records) {
    let key: string
    switch (dimension) {
      case 'agent':
        key = r.agent_id
        break
      case 'provider':
        key = r.provider
        break
      case 'department':
        key = agentDeptMap.get(r.agent_id) ?? 'Unknown'
        break
    }
    groups.set(key, (groups.get(key) ?? 0) + r.cost_usd)
    totalCost += r.cost_usd
  }

  const slices: BreakdownSlice[] = []
  let colorIdx = 0
  for (const [key, cost] of groups) {
    let label: string
    switch (dimension) {
      case 'agent':
        label = agentNameMap.get(key) ?? key
        break
      case 'provider':
      case 'department':
        label = key
        break
    }
    slices.push({
      key,
      label,
      cost,
      percent: totalCost > 0 ? (cost / totalCost) * 100 : 0,
      color: DONUT_COLORS[colorIdx % DONUT_COLORS.length]!,
    })
    colorIdx++
  }

  return slices.sort((a, b) => b.cost - a.cost)
}

/**
 * Compute cost category breakdown from cost records.
 *
 * Buckets records by `call_category` (null treated as uncategorized).
 * Returns cost, count, and percentage for each of the four categories.
 */
export function computeCategoryBreakdown(
  records: readonly CostRecord[],
): CategoryRatio {
  const buckets = {
    productive: { cost: 0, count: 0 },
    coordination: { cost: 0, count: 0 },
    system: { cost: 0, count: 0 },
    uncategorized: { cost: 0, count: 0 },
  }
  let totalCost = 0

  for (const r of records) {
    const cat = r.call_category ?? 'uncategorized'
    const bucket = buckets[cat] ?? buckets.uncategorized
    bucket.cost += r.cost_usd
    bucket.count += 1
    totalCost += r.cost_usd
  }

  const pct = (cost: number) => (totalCost > 0 ? (cost / totalCost) * 100 : 0)

  return {
    productive: { ...buckets.productive, percent: pct(buckets.productive.cost) },
    coordination: { ...buckets.coordination, percent: pct(buckets.coordination.cost) },
    system: { ...buckets.system, percent: pct(buckets.system.cost) },
    uncategorized: { ...buckets.uncategorized, percent: pct(buckets.uncategorized.cost) },
  }
}

/**
 * Determine which threshold zone the current budget usage falls in.
 */
export function getThresholdZone(
  usedPercent: number,
  alerts: BudgetAlertConfig,
): ThresholdZone {
  if (usedPercent >= alerts.hard_stop_at) return 'critical'
  if (usedPercent >= alerts.critical_at) return 'red'
  if (usedPercent >= alerts.warn_at) return 'amber'
  return 'normal'
}

/**
 * Compute a human-readable exhaustion date from days remaining.
 *
 * Returns `null` when `daysUntilExhausted` is `null` (no exhaustion projected).
 */
export function computeExhaustionDate(
  daysUntilExhausted: number | null,
): string | null {
  if (daysUntilExhausted === null) return null
  const date = new Date()
  date.setDate(date.getDate() + daysUntilExhausted)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Aggregate daily trend data points into ISO-week buckets (Monday-based).
 *
 * Each weekly point uses the Monday timestamp and the sum of daily values
 * in that week.
 */
export function aggregateWeekly(
  dataPoints: readonly TrendDataPoint[],
): TrendDataPoint[] {
  if (dataPoints.length === 0) return []

  const weeks = new Map<string, number>()

  for (const point of dataPoints) {
    const date = new Date(point.timestamp)
    const day = date.getUTCDay()
    // Shift to Monday-based: Sunday (0) becomes 6, Monday (1) becomes 0, etc.
    const shift = day === 0 ? 6 : day - 1
    const monday = new Date(date)
    monday.setUTCDate(monday.getUTCDate() - shift)
    const key = monday.toISOString().slice(0, 10)
    weeks.set(key, (weeks.get(key) ?? 0) + point.value)
  }

  const result: TrendDataPoint[] = []
  for (const [timestamp, value] of weeks) {
    result.push({ timestamp, value })
  }
  return result.sort((a, b) => a.timestamp.localeCompare(b.timestamp))
}

/**
 * Compute days remaining until the next billing cycle reset.
 */
export function daysUntilBudgetReset(resetDay: number): number {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth()
  const today = now.getDate()

  if (today < resetDay) {
    return resetDay - today
  }
  // Next reset is in the following month
  const nextMonth = new Date(year, month + 1, resetDay)
  const diff = nextMonth.getTime() - now.getTime()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

/**
 * Filter activities to only budget-related CFO events.
 */
export function filterCfoEvents(
  activities: readonly ActivityItem[],
): ActivityItem[] {
  return activities.filter((a) => CFO_EVENT_TYPES.has(a.action_type))
}

/**
 * Compute metric card data for the Budget page header.
 *
 * Returns an array of 4 card definitions matching the MetricCard props shape.
 */
export function computeBudgetMetricCards(
  overview: OverviewMetrics,
  budgetConfig: BudgetConfig | null,
  forecast: ForecastResponse | null,
): BudgetMetricCardData[] {
  const currency = overview.currency ?? budgetConfig?.currency
  const totalMonthly = budgetConfig?.total_monthly ?? 0

  const spendCard: BudgetMetricCardData = {
    label: 'SPEND THIS PERIOD',
    value: formatCurrency(overview.total_cost_usd, currency),
    sparklineData: overview.cost_7d_trend.map((p) => p.value),
    change: computeSpendTrend(overview.cost_7d_trend),
    ...(totalMonthly > 0 && {
      progress: { current: overview.total_cost_usd, total: totalMonthly },
      subText: `of ${formatCurrency(totalMonthly, currency)} budget`,
    }),
  }

  const remainingCard: BudgetMetricCardData = {
    label: 'BUDGET REMAINING',
    value: formatCurrency(overview.budget_remaining_usd, currency),
    subText: `${Math.round(Math.max(0, 100 - overview.budget_used_percent))}% of budget`,
  }

  const avgDayCard: BudgetMetricCardData = {
    label: 'AVG DAILY SPEND',
    value: formatCurrency(forecast?.avg_daily_spend_usd ?? 0, currency),
  }

  const daysLeftCard: BudgetMetricCardData = {
    label: 'DAYS UNTIL EXHAUSTED',
    value: forecast?.days_until_exhausted != null
      ? String(forecast.days_until_exhausted)
      : 'N/A',
    subText: forecast?.days_until_exhausted != null
      ? computeExhaustionDate(forecast.days_until_exhausted) ?? undefined
      : budgetConfig
        ? `Resets in ${daysUntilBudgetReset(budgetConfig.reset_day)} days`
        : undefined,
  }

  return [spendCard, remainingCard, avgDayCard, daysLeftCard]
}
