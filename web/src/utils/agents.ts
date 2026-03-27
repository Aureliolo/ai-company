/** Pure utility functions for agent data transformations. */

import {
  Activity,
  ArrowDownCircle,
  ArrowUpCircle,
  Briefcase,
  CheckCircle2,
  CircleDollarSign,
  Play,
  Send,
  Inbox,
  UserPlus,
  UserMinus,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import type {
  AgentConfig,
  AgentPerformanceSummary,
  AgentStatus,
  CareerEventType,
  DepartmentName,
  SeniorityLevel,
} from '@/api/types'
import type { MetricCardProps } from '@/components/ui/metric-card'
import type { AgentRuntimeStatus, SemanticColor } from '@/lib/utils'
import { formatCurrency } from '@/utils/format'

// ── Filter / Sort types ────────────────────────────────────

export interface AgentFilters {
  search?: string
  department?: DepartmentName
  level?: SeniorityLevel
  status?: AgentStatus
}

export type AgentSortKey = 'name' | 'department' | 'level' | 'status' | 'hiring_date'

// ── Status mapping ─────────────────────────────────────────

const STATUS_MAP: Record<AgentStatus, AgentRuntimeStatus> = {
  active: 'active',
  onboarding: 'idle',
  on_leave: 'idle',
  terminated: 'offline',
}

/** Map HR lifecycle AgentStatus to UI AgentRuntimeStatus. */
export function toRuntimeStatus(status: AgentStatus): AgentRuntimeStatus {
  return STATUS_MAP[status]
}

// ── Filtering ──────────────────────────────────────────────

/** Client-side filter agents by search, department, level, and status. */
export function filterAgents(
  agents: readonly AgentConfig[],
  filters: AgentFilters,
): AgentConfig[] {
  let result = [...agents]

  if (filters.department) {
    result = result.filter((a) => a.department === filters.department)
  }
  if (filters.level) {
    result = result.filter((a) => a.level === filters.level)
  }
  if (filters.status) {
    result = result.filter((a) => a.status === filters.status)
  }
  if (filters.search) {
    const q = filters.search.toLowerCase()
    result = result.filter(
      (a) => a.name.toLowerCase().includes(q) || a.role.toLowerCase().includes(q),
    )
  }

  return result
}

// ── Sorting ────────────────────────────────────────────────

// Semantic ordering for ordinal fields (lexicographic comparison is incorrect)
const LEVEL_RANK: Record<SeniorityLevel, number> = {
  junior: 0, mid: 1, senior: 2, lead: 3, principal: 4, director: 5, vp: 6, c_suite: 7,
}
const STATUS_RANK: Record<AgentStatus, number> = {
  active: 0, onboarding: 1, on_leave: 2, terminated: 3,
}

/** Sort agents by a given key. Does not mutate the input. */
export function sortAgents(
  agents: readonly AgentConfig[],
  sortBy: AgentSortKey,
  direction: 'asc' | 'desc' = 'asc',
): AgentConfig[] {
  const sorted = [...agents]
  const dir = direction === 'asc' ? 1 : -1

  sorted.sort((a, b) => {
    let va: string | number = a[sortBy]
    let vb: string | number = b[sortBy]

    // Use semantic rank for ordinal fields
    if (sortBy === 'level') {
      va = LEVEL_RANK[a.level]
      vb = LEVEL_RANK[b.level]
    } else if (sortBy === 'status') {
      va = STATUS_RANK[a.status]
      vb = STATUS_RANK[b.status]
    }

    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })

  return sorted
}

// ── Formatting ─────────────────────────────────────────────

/** Format seconds into a human-readable duration string. */
export function formatCompletionTime(seconds: number | null): string {
  if (seconds == null || seconds < 0) return '--'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

/** Format a cost value using the project's configured currency (defaults to EUR). */
export function formatCostPerTask(cost: number | null): string {
  if (cost == null) return '--'
  return formatCurrency(cost)
}

// ── Performance cards ──────────────────────────────────────

type PerformanceCardData = Omit<MetricCardProps, 'className'>

/** Map an AgentPerformanceSummary to 4 MetricCard props. */
export function computePerformanceCards(
  perf: AgentPerformanceSummary,
): PerformanceCardData[] {
  const taskSparkline = perf.windows.length >= 2
    ? perf.windows.map((w) => w.tasks_completed)
    : undefined

  return [
    {
      label: 'TASKS COMPLETED',
      value: perf.tasks_completed_total,
      subText: `${perf.tasks_completed_7d} this week`,
      sparklineData: taskSparkline,
    },
    {
      label: 'AVG COMPLETION TIME',
      value: formatCompletionTime(perf.avg_completion_time_seconds),
    },
    {
      label: 'SUCCESS RATE',
      value: perf.success_rate_percent != null ? `${perf.success_rate_percent.toFixed(1)}%` : '--',
      subText: perf.tasks_completed_30d > 0
        ? `across ${perf.tasks_completed_30d} tasks (30d)`
        : undefined,
    },
    {
      label: 'COST PER TASK',
      value: formatCostPerTask(perf.cost_per_task_usd),
    },
  ]
}

// ── Prose insights ─────────────────────────────────────────

/**
 * Generate 0-3 human-readable insight sentences from performance data.
 * The agent parameter is accepted for future personality-based insights but not yet used.
 */
export function generateInsights(
  _agent: AgentConfig,
  perf: AgentPerformanceSummary | null,
): string[] {
  if (!perf) return []

  const insights: string[] = []

  // Success rate insight
  if (perf.success_rate_percent != null && perf.tasks_completed_total > 0) {
    insights.push(
      `Success rate of ${perf.success_rate_percent.toFixed(1)}% across ${perf.tasks_completed_total} completed tasks.`,
    )
  }

  // Trend insight
  if (perf.trend_direction === 'improving') {
    insights.push('Performance trending upward over the recent window.')
  } else if (perf.trend_direction === 'declining') {
    insights.push('Performance has been declining -- may need attention.')
  }

  // Quality insight
  if (perf.quality_score != null && perf.quality_score >= 8.0) {
    insights.push(`Quality score of ${perf.quality_score.toFixed(1)}/10 -- consistently high output.`)
  }

  return insights.slice(0, 3)
}

// ── Career event colors ────────────────────────────────────

const CAREER_COLOR_MAP: Record<CareerEventType, SemanticColor> = {
  hired: 'success',
  promoted: 'accent',
  onboarded: 'accent',
  demoted: 'warning',
  fired: 'danger',
}

/** Map a career event type to its semantic color. */
export function getCareerEventColor(eventType: CareerEventType): SemanticColor {
  return CAREER_COLOR_MAP[eventType]
}

// ── Activity event icons ───────────────────────────────────

const ACTIVITY_ICON_MAP: Record<string, LucideIcon> = {
  hired: UserPlus,
  fired: UserMinus,
  promoted: ArrowUpCircle,
  demoted: ArrowDownCircle,
  onboarded: Briefcase,
  task_completed: CheckCircle2,
  task_started: Play,
  cost_incurred: CircleDollarSign,
  tool_used: Wrench,
  delegation_sent: Send,
  delegation_received: Inbox,
}

const FALLBACK_ICON: LucideIcon = Activity

/** Map an activity event type string to a Lucide icon component. */
export function getActivityEventIcon(eventType: string): LucideIcon {
  return ACTIVITY_ICON_MAP[eventType] ?? FALLBACK_ICON
}
