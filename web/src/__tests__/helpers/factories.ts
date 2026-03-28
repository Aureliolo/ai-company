import type {
  AgentActivityEvent,
  AgentConfig,
  AgentPerformanceSummary,
  ApprovalResponse,
  CareerEvent,
  CompanyConfig,
  Department,
  DepartmentHealth,
  Task,
} from '@/api/types'

export function makeTask(id: string, overrides?: Partial<Task>): Task
export function makeTask(id: string, title: string, overrides?: Partial<Task>): Task
export function makeTask(id: string, titleOrOverrides?: string | Partial<Task>, overrides?: Partial<Task>): Task {
  const title = typeof titleOrOverrides === 'string' ? titleOrOverrides : `Task ${id}`
  const finalOverrides = typeof titleOrOverrides === 'object' ? titleOrOverrides : overrides
  return {
    id,
    title,
    description: 'Description',
    type: 'development',
    status: 'assigned',
    priority: 'medium',
    project: 'test-project',
    created_by: 'agent-cto',
    assigned_to: 'agent-eng',
    reviewers: [],
    dependencies: [],
    artifacts_expected: [],
    acceptance_criteria: [],
    estimated_complexity: 'medium',
    budget_limit: 10,
    deadline: null,
    max_retries: 3,
    parent_task_id: null,
    delegation_chain: [],
    task_structure: null,
    coordination_topology: 'auto',
    version: 1,
    created_at: '2026-03-20T10:00:00Z',
    updated_at: '2026-03-25T14:00:00Z',
    ...finalOverrides,
  }
}

export function makeAgent(name: string, overrides?: Partial<AgentConfig>): AgentConfig {
  return {
    id: `agent-${name}`,
    name,
    role: 'Developer',
    department: 'engineering',
    level: 'mid',
    status: 'active',
    personality: {
      traits: ['analytical'],
      communication_style: 'direct',
      risk_tolerance: 'medium',
      creativity: 'medium',
      description: 'A test agent',
      openness: 0.7,
      conscientiousness: 0.8,
      extraversion: 0.5,
      agreeableness: 0.6,
      stress_response: 0.5,
      decision_making: 'analytical',
      collaboration: 'team',
      verbosity: 'balanced',
      conflict_approach: 'collaborate',
    },
    model: {
      provider: 'test-provider',
      model_id: 'test-medium-001',
      temperature: 0.7,
      max_tokens: 4096,
      fallback_model: null,
    },
    skills: { primary: ['coding'], secondary: ['testing'] },
    memory: { type: 'persistent', retention_days: null },
    tools: { access_level: 'standard', allowed: ['code_edit'], denied: [] },
    autonomy_level: 'semi',
    hiring_date: '2026-03-01T00:00:00Z',
    ...overrides,
  }
}

/** Intentionally accepts `string` for test flexibility (non-enum dept names). */
export function makeDepartment(name: string, overrides?: Partial<Department>): Department {
  return {
    name: name as Department['name'],
    display_name: name.charAt(0).toUpperCase() + name.slice(1),
    teams: [],
    ...overrides,
  }
}

export function makeCompanyConfig(overrides?: Partial<CompanyConfig>): CompanyConfig {
  return {
    company_name: 'Test Corp',
    agents: [
      makeAgent('alice', { department: 'engineering', role: 'Lead Developer', level: 'lead' }),
      makeAgent('bob', { department: 'engineering', role: 'Developer' }),
      makeAgent('carol', { department: 'product', role: 'Product Manager', level: 'senior' }),
    ],
    departments: [
      makeDepartment('engineering'),
      makeDepartment('product'),
    ],
    ...overrides,
  }
}

export function makeDepartmentHealth(name: string, overrides?: Partial<DepartmentHealth>): DepartmentHealth {
  return {
    name: name as DepartmentHealth['name'],
    display_name: name.charAt(0).toUpperCase() + name.slice(1),
    health_percent: 85,
    agent_count: 3,
    task_count: 5,
    cost_usd: 12.5,
    ...overrides,
  }
}

export function makeApproval(id: string, overrides?: Partial<ApprovalResponse>): ApprovalResponse {
  return {
    id,
    action_type: 'code:create',
    title: `Approval ${id}`,
    description: 'Test approval description',
    requested_by: 'agent-eng',
    risk_level: 'medium',
    status: 'pending',
    task_id: null,
    metadata: {},
    decided_by: null,
    decision_reason: null,
    created_at: new Date(Date.now() - 3600_000).toISOString(), // 1 hour ago
    decided_at: null,
    expires_at: null,
    seconds_remaining: null,
    urgency_level: 'no_expiry',
    ...overrides,
  }
}

export function makeActivityEvent(overrides?: Partial<AgentActivityEvent>): AgentActivityEvent {
  return {
    event_type: 'task_completed',
    timestamp: '2026-03-25T12:00:00Z',
    description: 'Completed task task-1',
    related_ids: {},
    ...overrides,
  }
}

export function makeCareerEvent(overrides?: Partial<CareerEvent>): CareerEvent {
  return {
    event_type: 'hired',
    timestamp: '2026-03-01T00:00:00Z',
    description: 'Hired as Developer',
    initiated_by: 'system',
    metadata: {},
    ...overrides,
  }
}

export function makePerformanceSummary(
  agentName: string,
  overrides?: Partial<AgentPerformanceSummary>,
): AgentPerformanceSummary {
  return {
    agent_name: agentName,
    tasks_completed_total: 10,
    tasks_completed_7d: 3,
    tasks_completed_30d: 8,
    avg_completion_time_seconds: 3600,
    success_rate_percent: 90,
    cost_per_task_usd: 0.5,
    quality_score: 8.5,
    collaboration_score: 7.0,
    trend_direction: 'stable',
    windows: [],
    trends: [],
    ...overrides,
  }
}
