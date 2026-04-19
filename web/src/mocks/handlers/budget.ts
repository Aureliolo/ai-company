import { http, HttpResponse } from 'msw'
import type {
  getAgentSpending,
  getBudgetConfig,
} from '@/api/endpoints/budget'
import type { AgentSpending, BudgetConfig } from '@/api/types'
import { successFor } from './helpers'

const DEFAULT_CURRENCY = 'USD'

export function buildBudgetConfig(
  overrides: Partial<BudgetConfig> = {},
): BudgetConfig {
  return {
    total_monthly: 0,
    alerts: { warn_at: 0.8, critical_at: 0.9, hard_stop_at: 1 },
    per_task_limit: 10,
    per_agent_daily_limit: 50,
    auto_downgrade: {
      enabled: false,
      threshold: 0.8,
      downgrade_map: [],
      boundary: 'task_assignment',
    },
    reset_day: 1,
    currency: DEFAULT_CURRENCY,
    ...overrides,
  }
}

export const budgetHandlers = [
  http.get('/api/v1/budget/config', () =>
    HttpResponse.json(successFor<typeof getBudgetConfig>(buildBudgetConfig())),
  ),
  http.get('/api/v1/budget/records', () =>
    HttpResponse.json({
      success: true,
      data: [],
      error: null,
      error_detail: null,
      pagination: { total: 0, offset: 0, limit: 200 },
      daily_summary: [],
      period_summary: {
        avg_cost: 0,
        total_cost: 0,
        total_input_tokens: 0,
        total_output_tokens: 0,
        record_count: 0,
        currency: DEFAULT_CURRENCY,
      },
      currency: DEFAULT_CURRENCY,
    }),
  ),
  http.get('/api/v1/budget/agents/:agentId', ({ params }) =>
    HttpResponse.json(
      successFor<typeof getAgentSpending>({
        agent_id: String(params.agentId),
        total_cost: 0,
        currency: DEFAULT_CURRENCY,
      } satisfies AgentSpending),
    ),
  ),
]
