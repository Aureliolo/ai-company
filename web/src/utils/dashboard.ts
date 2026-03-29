import {
  DEPARTMENT_NAME_VALUES,
} from '@/api/types'
import type {
  ActivityItem,
  BudgetConfig,
  DepartmentHealth,
  DepartmentName,
  OverviewMetrics,
  TrendDataPoint,
  WsEvent,
  WsEventType,
} from '@/api/types'
import type { MetricCardProps } from '@/components/ui/metric-card'
import { formatCurrency } from '@/utils/format'

export type DashboardMetricCardData = Omit<MetricCardProps, 'className'>

const VALID_DEPARTMENT_NAMES: ReadonlySet<string> = new Set<string>(DEPARTMENT_NAME_VALUES)

const EVENT_DESCRIPTIONS: Partial<Record<WsEventType, string>> = {
  'task.created': 'created a task',
  'task.updated': 'updated a task',
  'task.status_changed': 'changed task status',
  'task.assigned': 'was assigned a task',
  'agent.hired': 'joined the organization',
  'agent.fired': 'left the organization',
  'agent.status_changed': 'changed status',
  'budget.record_added': 'recorded a cost',
  'budget.alert': 'triggered a budget alert',
  'message.sent': 'sent a message',
  'system.error': 'reported a system error',
  'system.startup': 'system started',
  'system.shutdown': 'system shutting down',
  'approval.submitted': 'submitted an approval request',
  'approval.approved': 'approved a request',
  'approval.rejected': 'rejected a request',
  'approval.expired': 'approval expired',
  'meeting.started': 'started a meeting',
  'meeting.completed': 'completed a meeting',
  'meeting.failed': 'meeting failed',
  'coordination.started': 'started coordination',
  'coordination.phase_completed': 'completed a coordination phase',
  'coordination.completed': 'completed coordination',
  'coordination.failed': 'coordination failed',
}

export function computeMetricCards(
  overview: OverviewMetrics,
  budget: BudgetConfig | null,
): DashboardMetricCardData[] {
  const spendTrend = computeSpendTrend(overview.cost_7d_trend)

  return [
    {
      label: 'TASKS',
      value: overview.total_tasks,
      subText: `${overview.tasks_by_status.completed ?? 0} completed`,
    },
    {
      label: 'ACTIVE AGENTS',
      value: overview.active_agents_count,
      subText: `${overview.idle_agents_count} idle`,
    },
    {
      label: 'SPEND',
      value: formatCurrency(overview.total_cost_usd, overview.currency),
      sparklineData:
        overview.cost_7d_trend.length >= 2
          ? overview.cost_7d_trend.map((p) => p.value)
          : undefined,
      change: spendTrend,
      progress: budget
        ? { current: Math.min(overview.total_cost_usd, budget.total_monthly), total: budget.total_monthly }
        : undefined,
      subText: `${Math.round(overview.budget_used_percent)}% of budget`,
    },
    {
      label: 'IN REVIEW',
      value: overview.tasks_by_status.in_review ?? 0,
    },
  ]
}

export function computeSpendTrend(
  points: readonly TrendDataPoint[],
): { value: number; direction: 'up' | 'down' } | undefined {
  if (points.length < 2) return undefined
  const first = points[0]!.value
  const last = points[points.length - 1]!.value
  if (first === 0) return undefined
  const pct = Math.round(Math.abs(((last - first) / first) * 100))
  if (pct === 0) return undefined
  return { value: pct, direction: last >= first ? 'up' : 'down' }
}

export function computeOrgHealth(departments: readonly DepartmentHealth[]): number | null {
  if (departments.length === 0) return null
  const valid = departments.filter((d) => Number.isFinite(d.health_percent))
  if (valid.length < departments.length) {
    console.warn(
      `[dashboard] computeOrgHealth: ${departments.length - valid.length} department(s) had non-finite health_percent`,
      departments.filter((d) => !Number.isFinite(d.health_percent)).map((d) => d.name),
    )
  }
  if (valid.length === 0) return null
  const sum = valid.reduce((acc, d) => acc + d.health_percent, 0)
  return Math.round(sum / valid.length)
}

export function describeEvent(eventType: WsEventType): string {
  return EVENT_DESCRIPTIONS[eventType] ?? eventType.replace(/[._]/g, ' ')
}

let wsActivityCounter = 0

export function wsEventToActivityItem(event: WsEvent): ActivityItem {
  const payload = event.payload ?? {}
  const agentName =
    (typeof payload.agent_name === 'string' && payload.agent_name) ||
    (typeof payload.assigned_to === 'string' && payload.assigned_to) ||
    'System'
  const taskId =
    typeof payload.task_id === 'string' ? payload.task_id : null
  const department =
    typeof payload.department === 'string' && VALID_DEPARTMENT_NAMES.has(payload.department)
      ? (payload.department as DepartmentName)
      : null

  const description =
    typeof payload.description === 'string' && payload.description
      ? payload.description
      : describeEvent(event.event_type)

  return {
    id: (typeof payload.id === 'string' && payload.id)
      || taskId
      || `${event.timestamp}-${event.event_type}-${agentName}-${++wsActivityCounter}`,
    timestamp: event.timestamp,
    agent_name: agentName,
    action_type: event.event_type,
    description,
    task_id: taskId,
    department,
  }
}
