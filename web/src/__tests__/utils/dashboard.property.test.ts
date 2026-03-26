import * as fc from 'fast-check'
import {
  computeMetricCards,
  computeOrgHealth,
  describeEvent,
  wsEventToActivityItem,
} from '@/utils/dashboard'
import type { BudgetConfig, DepartmentHealth, DepartmentName, OverviewMetrics, TrendDataPoint, WsEvent, WsEventType } from '@/api/types'

const WS_EVENT_TYPES: WsEventType[] = [
  'task.created', 'task.updated', 'task.status_changed', 'task.assigned',
  'agent.hired', 'agent.fired', 'agent.status_changed',
  'budget.record_added', 'budget.alert',
  'message.sent',
  'system.error', 'system.startup', 'system.shutdown',
  'approval.submitted', 'approval.approved', 'approval.rejected', 'approval.expired',
  'meeting.started', 'meeting.completed', 'meeting.failed',
  'coordination.started', 'coordination.phase_completed', 'coordination.completed', 'coordination.failed',
]

const DEPT_NAMES: DepartmentName[] = [
  'executive', 'product', 'design', 'engineering',
  'quality_assurance', 'data_analytics', 'operations',
  'creative_marketing', 'security',
]

const arbIsoTimestamp = fc.integer({ min: 1735689600000, max: 1767225600000 }).map(
  (ms) => new Date(ms).toISOString(),
)

const arbTrendPoint: fc.Arbitrary<TrendDataPoint> = fc.record({
  timestamp: arbIsoTimestamp,
  value: fc.float({ min: 0, max: 10000, noNaN: true }),
})

const arbOverview: fc.Arbitrary<OverviewMetrics> = fc.record({
  total_tasks: fc.nat({ max: 10000 }),
  tasks_by_status: fc.record({
    created: fc.nat({ max: 100 }),
    assigned: fc.nat({ max: 100 }),
    in_progress: fc.nat({ max: 100 }),
    in_review: fc.nat({ max: 100 }),
    completed: fc.nat({ max: 100 }),
    blocked: fc.nat({ max: 100 }),
    failed: fc.nat({ max: 100 }),
    interrupted: fc.nat({ max: 100 }),
    cancelled: fc.nat({ max: 100 }),
  }),
  total_agents: fc.nat({ max: 100 }),
  total_cost_usd: fc.float({ min: 0, max: 100000, noNaN: true }),
  budget_remaining_usd: fc.float({ min: 0, max: 100000, noNaN: true }),
  budget_used_percent: fc.float({ min: 0, max: 100, noNaN: true }),
  cost_7d_trend: fc.array(arbTrendPoint, { minLength: 0, maxLength: 14 }),
  active_agents_count: fc.nat({ max: 100 }),
  idle_agents_count: fc.nat({ max: 100 }),
})

const arbBudgetConfig: fc.Arbitrary<BudgetConfig> = fc.record({
  total_monthly: fc.float({ min: 1, max: 100000, noNaN: true }),
  alerts: fc.record({
    warn_at: fc.nat({ max: 100 }),
    critical_at: fc.nat({ max: 100 }),
    hard_stop_at: fc.nat({ max: 100 }),
  }),
  per_task_limit: fc.float({ min: 0, max: 1000, noNaN: true }),
  per_agent_daily_limit: fc.float({ min: 0, max: 1000, noNaN: true }),
  auto_downgrade: fc.record({
    enabled: fc.boolean(),
    threshold: fc.nat({ max: 100 }),
    downgrade_map: fc.constant([] as [string, string][]),
    boundary: fc.constant('task_assignment' as const),
  }),
  reset_day: fc.integer({ min: 1, max: 28 }),
})

describe('computeMetricCards (properties)', () => {
  it('always returns exactly 4 cards', () => {
    fc.assert(
      fc.property(arbOverview, arbBudgetConfig, (overview, budget) => {
        const cards = computeMetricCards(overview, budget)
        expect(cards).toHaveLength(4)
      }),
    )
  })

  it('every card has a non-empty label', () => {
    fc.assert(
      fc.property(arbOverview, arbBudgetConfig, (overview, budget) => {
        const cards = computeMetricCards(overview, budget)
        for (const card of cards) {
          expect(card.label.length).toBeGreaterThan(0)
        }
      }),
    )
  })

  it('progress current never exceeds total', () => {
    fc.assert(
      fc.property(arbOverview, arbBudgetConfig, (overview, budget) => {
        const cards = computeMetricCards(overview, budget)
        for (const card of cards) {
          if (card.progress) {
            expect(card.progress.current).toBeLessThanOrEqual(card.progress.total)
          }
        }
      }),
    )
  })
})

describe('computeOrgHealth (properties)', () => {
  it('returns a value in [0, 100]', () => {
    const arbDeptHealth: fc.Arbitrary<DepartmentHealth> = fc.record({
      name: fc.constantFrom(...DEPT_NAMES),
      display_name: fc.string({ minLength: 1 }),
      health_percent: fc.float({ min: 0, max: 100, noNaN: true }),
      agent_count: fc.nat({ max: 50 }),
      task_count: fc.nat({ max: 200 }),
      cost_usd: fc.option(fc.float({ min: 0, max: 10000, noNaN: true }), { nil: null }),
    })

    fc.assert(
      fc.property(fc.array(arbDeptHealth, { minLength: 0, maxLength: 9 }), (depts) => {
        const result = computeOrgHealth(depts)
        expect(result).toBeGreaterThanOrEqual(0)
        expect(result).toBeLessThanOrEqual(100)
      }),
    )
  })
})

describe('describeEvent (properties)', () => {
  it('returns a non-empty string for every known event type', () => {
    fc.assert(
      fc.property(fc.constantFrom(...WS_EVENT_TYPES), (eventType) => {
        const description = describeEvent(eventType)
        expect(description.length).toBeGreaterThan(0)
      }),
    )
  })
})

describe('wsEventToActivityItem (properties)', () => {
  it('always produces a valid ActivityItem', () => {
    const arbWsEvent: fc.Arbitrary<WsEvent> = fc.record({
      event_type: fc.constantFrom(...WS_EVENT_TYPES),
      channel: fc.constantFrom('tasks', 'agents', 'budget', 'messages', 'system', 'approvals', 'meetings') as fc.Arbitrary<WsEvent['channel']>,
      timestamp: arbIsoTimestamp,
      payload: fc.record({
        agent_name: fc.option(fc.string({ minLength: 1, maxLength: 30 }), { nil: undefined }),
        task_id: fc.option(fc.uuid(), { nil: undefined }),
      }) as fc.Arbitrary<Record<string, unknown>>,
    })

    fc.assert(
      fc.property(arbWsEvent, (event) => {
        const item = wsEventToActivityItem(event)
        expect(item.id).toBeTruthy()
        expect(item.agent_name).toBeTruthy()
        expect(item.description).toBeTruthy()
        expect(item.timestamp).toBe(event.timestamp)
        expect(item.action_type).toBe(event.event_type)
      }),
    )
  })
})
