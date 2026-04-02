/** TypeScript interfaces mirroring backend Pydantic DTOs and domain models. */

// ── Enums ────────────────────────────────────────────────────

export type TaskStatus =
  | 'created'
  | 'assigned'
  | 'in_progress'
  | 'in_review'
  | 'completed'
  | 'blocked'
  | 'failed'
  | 'interrupted'
  | 'cancelled'

export type TaskType =
  | 'development'
  | 'design'
  | 'research'
  | 'review'
  | 'meeting'
  | 'admin'

export type Priority = 'critical' | 'high' | 'medium' | 'low'

export type Complexity = 'simple' | 'medium' | 'complex' | 'epic'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export type ApprovalRiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type UrgencyLevel = 'critical' | 'high' | 'normal' | 'no_expiry'

export type SeniorityLevel =
  | 'junior'
  | 'mid'
  | 'senior'
  | 'lead'
  | 'principal'
  | 'director'
  | 'vp'
  | 'c_suite'

export type AgentStatus = 'active' | 'onboarding' | 'on_leave' | 'terminated'

export const SENIORITY_LEVEL_VALUES = [
  'junior', 'mid', 'senior', 'lead', 'principal', 'director', 'vp', 'c_suite',
] as const satisfies readonly SeniorityLevel[]

export const AGENT_STATUS_VALUES = [
  'active', 'onboarding', 'on_leave', 'terminated',
] as const satisfies readonly AgentStatus[]

export type AutonomyLevel = 'full' | 'semi' | 'supervised' | 'locked'

export type HumanRole =
  | 'ceo'
  | 'manager'
  | 'board_member'
  | 'pair_programmer'
  | 'observer'
  | 'system'

export type DepartmentName =
  | 'executive'
  | 'product'
  | 'design'
  | 'engineering'
  | 'quality_assurance'
  | 'data_analytics'
  | 'operations'
  | 'creative_marketing'
  | 'security'

export type ProjectStatus =
  | 'planning'
  | 'active'
  | 'on_hold'
  | 'completed'
  | 'cancelled'

export const PROJECT_STATUS_VALUES = [
  'planning', 'active', 'on_hold', 'completed', 'cancelled',
] as const satisfies readonly ProjectStatus[]

export type ArtifactType = 'code' | 'tests' | 'documentation'

export const ARTIFACT_TYPE_VALUES = [
  'code', 'tests', 'documentation',
] as const satisfies readonly ArtifactType[]

export type RiskTolerance = 'low' | 'medium' | 'high'

export type CreativityLevel = 'low' | 'medium' | 'high'

export type DecisionMakingStyle = 'analytical' | 'intuitive' | 'consultative' | 'directive'

export type CollaborationPreference = 'independent' | 'pair' | 'team'

export type CommunicationVerbosity = 'terse' | 'balanced' | 'verbose'

export type ConflictApproach = 'avoid' | 'accommodate' | 'compete' | 'compromise' | 'collaborate'

export type TaskStructure = 'sequential' | 'parallel' | 'mixed'

export type CoordinationTopology = 'sas' | 'centralized' | 'decentralized' | 'context_dependent' | 'auto'

export type ToolAccessLevel = 'sandboxed' | 'restricted' | 'standard' | 'elevated' | 'custom'

export type MemoryLevel = 'persistent' | 'project' | 'session' | 'none'

// ── RFC 9457 Structured Errors ───────────────────────────────

export type ErrorCategory =
  | 'auth'
  | 'validation'
  | 'not_found'
  | 'conflict'
  | 'rate_limit'
  | 'budget_exhausted'
  | 'provider_error'
  | 'internal'

export type ErrorCode =
  | 1000 | 1001
  | 2000 | 2001
  | 3000 | 3001 | 3002
  | 4000 | 4001
  | 5000
  | 6000
  | 7000
  | 8000 | 8001 | 8002

export interface ErrorDetail {
  detail: string
  error_code: ErrorCode
  error_category: ErrorCategory
  retryable: boolean
  retry_after: number | null
  instance: string
  title: string
  type: string
}

// ── Response Envelopes ───────────────────────────────────────

/** Discriminated API response envelope. */
export type ApiResponse<T> =
  | { data: T; error: null; error_detail: null; success: true }
  | { data: null; error: string; error_detail: ErrorDetail; success: false }

export interface PaginationMeta {
  total: number
  offset: number
  limit: number
}

/** Discriminated paginated response envelope. */
export type PaginatedResponse<T> =
  | { data: T[]; error: null; error_detail: null; success: true; pagination: PaginationMeta; degraded_sources?: readonly string[] }
  | { data: null; error: string; error_detail: ErrorDetail; success: false; pagination: null; degraded_sources?: readonly string[] }

// ── Auth ─────────────────────────────────────────────────────

export interface CredentialsRequest {
  username: string
  password: string
}

/** Alias for setup endpoint. */
export type SetupRequest = CredentialsRequest

/** Alias for login endpoint. */
export type LoginRequest = CredentialsRequest

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface TokenResponse {
  token: string
  expires_in: number
  must_change_password: boolean
}

export interface WsTicketResponse {
  ticket: string
  expires_in: number
}

export interface UserInfoResponse {
  id: string
  username: string
  role: HumanRole
  must_change_password: boolean
}

// ── Tasks ────────────────────────────────────────────────────

export interface AcceptanceCriterion {
  description: string
  met: boolean
}

export interface ExpectedArtifact {
  name: string
  type: string
}

export interface Task {
  id: string
  title: string
  description: string
  type: TaskType
  status: TaskStatus
  priority: Priority
  project: string
  created_by: string
  assigned_to: string | null
  readonly reviewers: readonly string[]
  readonly dependencies: readonly string[]
  readonly artifacts_expected: readonly ExpectedArtifact[]
  readonly acceptance_criteria: readonly AcceptanceCriterion[]
  estimated_complexity: Complexity
  budget_limit: number
  cost_usd?: number
  deadline: string | null
  max_retries: number
  parent_task_id: string | null
  readonly delegation_chain: readonly string[]
  task_structure: TaskStructure | null
  coordination_topology: CoordinationTopology
  version?: number
  created_at?: string
  updated_at?: string
}

export interface CreateTaskRequest {
  title: string
  description: string
  type: TaskType
  priority?: Priority
  project: string
  created_by: string
  assigned_to?: string | null
  estimated_complexity?: Complexity
  budget_limit?: number
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  priority?: Priority
  assigned_to?: string | null
  budget_limit?: number
  expected_version?: number
}

export interface TransitionTaskRequest {
  target_status: TaskStatus
  assigned_to?: string | null
  expected_version?: number
}

export interface CancelTaskRequest {
  reason: string
}

export interface TaskFilters {
  status?: TaskStatus
  assigned_to?: string
  project?: string
  offset?: number
  limit?: number
}

// ── Approvals ────────────────────────────────────────────────

export interface ApprovalItem {
  id: string
  action_type: string
  title: string
  description: string
  requested_by: string
  risk_level: ApprovalRiskLevel
  status: ApprovalStatus
  task_id: string | null
  metadata: Record<string, string>
  decided_by: string | null
  decision_reason: string | null
  created_at: string
  decided_at: string | null
  expires_at: string | null
}

export interface ApprovalResponse extends ApprovalItem {
  seconds_remaining: number | null
  urgency_level: UrgencyLevel
}

export interface CreateApprovalRequest {
  action_type: string
  title: string
  description: string
  risk_level: ApprovalRiskLevel
  ttl_seconds?: number
  task_id?: string
  metadata?: Record<string, string>
}

export interface ApproveRequest {
  comment?: string
}

export interface RejectRequest {
  reason: string
}

export interface ApprovalFilters {
  status?: ApprovalStatus
  risk_level?: ApprovalRiskLevel
  action_type?: string
  offset?: number
  limit?: number
}

// ── Agents ───────────────────────────────────────────────────

/**
 * Agent configuration as returned by the /agents API endpoints.
 *
 * Matches the backend AgentConfig Pydantic model (config/schema.py).
 * Runtime fields (id, status, hiring_date) are optional -- they exist
 * on AgentIdentity but may not be present in config-level responses.
 */
export interface AgentConfig {
  id?: string
  name: string
  role: string
  department: DepartmentName
  level: SeniorityLevel
  status?: AgentStatus
  personality: Record<string, unknown>
  model: Record<string, unknown>
  memory: Record<string, unknown>
  tools: Record<string, unknown>
  authority: Record<string, unknown>
  autonomy_level: AutonomyLevel | null
  hiring_date?: string
}

// ── Agent Performance ────────────────────────────────────────

export type TrendDirection = 'improving' | 'stable' | 'declining' | 'insufficient_data'

export const TREND_DIRECTION_VALUES = [
  'improving', 'stable', 'declining', 'insufficient_data',
] as const satisfies readonly TrendDirection[]

/**
 * Aggregate metrics for a rolling time window.
 * Invariant: tasks_completed + tasks_failed === data_point_count (enforced server-side).
 */
export interface WindowMetrics {
  window_size: string
  data_point_count: number
  tasks_completed: number
  tasks_failed: number
  avg_quality_score: number | null
  avg_cost_per_task: number | null
  avg_completion_time_seconds: number | null
  avg_tokens_per_task: number | null
  success_rate: number | null
  collaboration_score: number | null
}

export interface TrendResult {
  metric_name: string
  window_size: string
  direction: TrendDirection
  slope: number
  data_point_count: number
}

export interface AgentPerformanceSummary {
  agent_name: string
  tasks_completed_total: number
  tasks_completed_7d: number
  tasks_completed_30d: number
  avg_completion_time_seconds: number | null
  success_rate_percent: number | null
  cost_per_task_usd: number | null
  quality_score: number | null
  collaboration_score: number | null
  trend_direction: TrendDirection
  readonly windows: readonly WindowMetrics[]
  readonly trends: readonly TrendResult[]
}

// ── Agent Activity & Career ─────────────────────────────────

export type ActivityEventType =
  | 'hired' | 'fired' | 'promoted' | 'demoted' | 'onboarded'
  | 'offboarded' | 'status_changed'
  | 'task_completed' | 'task_started'
  | 'cost_incurred'
  | 'tool_used'
  | 'delegation_sent' | 'delegation_received'

export const ACTIVITY_EVENT_TYPE_VALUES = [
  'hired', 'fired', 'promoted', 'demoted', 'onboarded',
  'offboarded', 'status_changed',
  'task_completed', 'task_started',
  'cost_incurred',
  'tool_used',
  'delegation_sent', 'delegation_received',
] as const satisfies readonly ActivityEventType[]

export interface AgentActivityEvent {
  event_type: ActivityEventType | (string & {})
  timestamp: string
  description: string
  readonly related_ids: Readonly<Record<string, string>>
}

export type CareerEventType = 'hired' | 'fired' | 'promoted' | 'demoted' | 'onboarded'

export const CAREER_EVENT_TYPE_VALUES = [
  'hired', 'fired', 'promoted', 'demoted', 'onboarded',
] as const satisfies readonly CareerEventType[]

export interface CareerEvent {
  event_type: CareerEventType
  timestamp: string
  description: string
  initiated_by: string
  readonly metadata: Readonly<Record<string, string>>
}

// ── Budget ───────────────────────────────────────────────────

export interface CostRecord {
  agent_id: string
  task_id: string
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  timestamp: string
  call_category: 'productive' | 'coordination' | 'system' | null
}

export interface DailySummary {
  date: string
  total_cost_usd: number
  total_input_tokens: number
  total_output_tokens: number
  record_count: number
  currency: string
}

export interface PeriodSummary {
  avg_cost_usd: number
  total_cost_usd: number
  total_input_tokens: number
  total_output_tokens: number
  record_count: number
  currency: string
}

export interface BudgetAlertConfig {
  warn_at: number
  critical_at: number
  hard_stop_at: number
}

export interface AutoDowngradeConfig {
  enabled: boolean
  threshold: number
  readonly downgrade_map: readonly [string, string][]
  boundary: 'task_assignment'
}

export interface BudgetConfig {
  total_monthly: number
  alerts: BudgetAlertConfig
  per_task_limit: number
  per_agent_daily_limit: number
  auto_downgrade: AutoDowngradeConfig
  reset_day: number
  currency: string
}

export interface AgentSpending {
  agent_id: string
  total_cost_usd: number
  currency: string
}

// ── Analytics ────────────────────────────────────────────────

export interface OverviewMetrics {
  total_tasks: number
  tasks_by_status: Record<TaskStatus, number>
  total_agents: number
  total_cost_usd: number
  budget_remaining_usd: number
  budget_used_percent: number
  cost_7d_trend: readonly TrendDataPoint[]
  active_agents_count: number
  idle_agents_count: number
  currency: string
}

export type TrendPeriod = '7d' | '30d' | '90d'

export type TrendMetric = 'spend' | 'tasks_completed' | 'success_rate' | 'active_agents'

export type BucketSize = 'hour' | 'day'

export interface TrendDataPoint {
  timestamp: string
  value: number
}

export interface TrendsResponse {
  period: TrendPeriod
  metric: TrendMetric
  bucket_size: BucketSize
  readonly data_points: readonly TrendDataPoint[]
}

export interface ForecastPoint {
  day: string
  projected_spend_usd: number
}

export interface ForecastResponse {
  horizon_days: number
  projected_total_usd: number
  readonly daily_projections: readonly ForecastPoint[]
  days_until_exhausted: number | null
  confidence: number
  avg_daily_spend_usd: number
  currency: string
}

// ── Activities ──────────────────────────────────────────────

/** Activity event as returned by the backend REST API. */
export interface ActivityEvent {
  event_type: ActivityEventType
  timestamp: string
  description: string
  related_ids: Record<string, string>
}

/**
 * Legacy display-oriented activity item derived from {@link ActivityEvent}.
 * Used by the dashboard ActivityFeed component.
 */
export interface ActivityItem {
  id: string
  timestamp: string
  agent_name: string
  /** REST path produces ActivityEventType; WS path produces WsEventType. */
  action_type: ActivityEventType | WsEventType
  description: string
  task_id: string | null
  department: DepartmentName | null
}

// ── Department Health ───────────────────────────────────────

/**
 * Department-level health aggregation as returned by the backend.
 * Matches the Pydantic DepartmentHealth model in controllers/departments.py.
 */
export interface DepartmentHealth {
  department_name: DepartmentName
  agent_count: number
  active_agent_count: number
  /** ISO 4217 currency code (e.g. "EUR", "USD"). */
  currency: string
  /** Mean quality score across agents, 0.0 to 10.0, or null when insufficient data. */
  avg_performance_score: number | null
  department_cost_7d: number
  readonly cost_trend: readonly TrendDataPoint[]
  /** Mean collaboration score, 0.0 to 10.0, or null when insufficient data. */
  collaboration_score: number | null
  /** Backend-computed: active_agent_count / agent_count * 100. */
  utilization_percent: number
}

// ── Company / Organization ───────────────────────────────────

export interface Department {
  name: DepartmentName
  display_name?: string
  head?: string | null
  head_id?: string | null
  budget_percent?: number
  readonly teams: readonly TeamConfig[]
  autonomy_level?: AutonomyLevel | null
}

export interface TeamConfig {
  name: string
  lead?: string
  readonly members: readonly string[]
}

export interface CompanyConfig {
  company_name: string
  autonomy_level?: AutonomyLevel
  budget_monthly?: number
  communication_pattern?: string
  readonly agents: readonly AgentConfig[]
  readonly departments: readonly Department[]
}

// ── Company Mutation Requests ────────────────────────────────

export interface UpdateCompanyRequest {
  company_name?: string
  autonomy_level?: AutonomyLevel
  budget_monthly?: number
  communication_pattern?: string
}

export interface CreateDepartmentRequest {
  name: string
  display_name: string
  head?: string | null
  budget_percent?: number
  autonomy_level?: AutonomyLevel | null
}

export interface UpdateDepartmentRequest {
  display_name?: string
  head?: string | null
  budget_percent?: number
  autonomy_level?: AutonomyLevel | null
  teams?: readonly TeamConfig[]
}

export interface ReorderDepartmentsRequest {
  readonly department_names: readonly string[]
}

export interface CreateAgentOrgRequest {
  name: string
  role: string
  department: DepartmentName
  level: SeniorityLevel
  personality_preset?: string
  model_provider?: string
  model_id?: string
}

export interface UpdateAgentOrgRequest {
  name?: string
  role?: string
  department?: DepartmentName
  level?: SeniorityLevel
  status?: AgentStatus
  autonomy_level?: AutonomyLevel | null
}

export interface ReorderAgentsRequest {
  readonly agent_ids: readonly string[]
}

// ── Providers ────────────────────────────────────────────────

export type AuthType = 'api_key' | 'oauth' | 'custom_header' | 'subscription' | 'none'

export type ProviderHealthStatus = 'up' | 'degraded' | 'down' | 'unknown'

export interface ProviderHealthSummary {
  last_check_timestamp: string | null
  avg_response_time_ms: number | null
  error_rate_percent_24h: number
  calls_last_24h: number
  health_status: ProviderHealthStatus
  total_tokens_24h: number
  total_cost_24h: number
}

export interface ProviderModelConfig {
  id: string
  alias: string | null
  cost_per_1k_input: number
  cost_per_1k_output: number
  max_context: number
  estimated_latency_ms: number | null
}

export interface ProviderModelResponse {
  id: string
  alias: string | null
  cost_per_1k_input: number
  cost_per_1k_output: number
  max_context: number
  estimated_latency_ms: number | null
  supports_tools: boolean
  supports_vision: boolean
  supports_streaming: boolean
}

/**
 * Provider response DTO -- secrets stripped, credential indicators provided.
 */
export interface ProviderConfig {
  driver: string
  litellm_provider: string | null
  auth_type: AuthType
  base_url: string | null
  readonly models: readonly ProviderModelConfig[]
  has_api_key: boolean
  has_oauth_credentials: boolean
  has_custom_header: boolean
  has_subscription_token: boolean
  tos_accepted_at: string | null
  oauth_token_url: string | null
  oauth_client_id: string | null
  oauth_scope: string | null
  custom_header_name: string | null
}

export interface CreateProviderRequest {
  name: string
  driver?: string
  litellm_provider?: string
  auth_type?: AuthType
  api_key?: string
  subscription_token?: string
  tos_accepted?: boolean
  base_url?: string
  oauth_token_url?: string
  oauth_client_id?: string
  oauth_client_secret?: string
  oauth_scope?: string
  custom_header_name?: string
  custom_header_value?: string
  models?: readonly ProviderModelConfig[]
}

export interface UpdateProviderRequest {
  driver?: string
  litellm_provider?: string
  auth_type?: AuthType
  api_key?: string
  clear_api_key?: boolean
  subscription_token?: string
  clear_subscription_token?: boolean
  tos_accepted?: boolean
  base_url?: string | null
  oauth_token_url?: string | null
  oauth_client_id?: string | null
  oauth_client_secret?: string | null
  oauth_scope?: string | null
  custom_header_name?: string | null
  custom_header_value?: string | null
  models?: readonly ProviderModelConfig[]
}

export interface TestConnectionRequest {
  model?: string
}

export interface TestConnectionResponse {
  success: boolean
  latency_ms: number | null
  error: string | null
  model_tested: string | null
}

export interface ProviderPreset {
  name: string
  display_name: string
  description: string
  driver: string
  litellm_provider: string
  auth_type: AuthType
  readonly supported_auth_types: readonly AuthType[]
  default_base_url: string | null
  requires_base_url: boolean
  readonly candidate_urls: readonly string[]
  readonly default_models: readonly ProviderModelConfig[]
}

export interface ProbePresetResponse {
  url: string | null
  model_count: number
  candidates_tried: number
}

export interface CreateFromPresetRequest {
  preset_name: string
  name: string
  auth_type?: AuthType
  api_key?: string
  subscription_token?: string
  tos_accepted?: boolean
  base_url?: string
  models?: readonly ProviderModelConfig[]
}

export interface DiscoverModelsResponse {
  readonly discovered_models: readonly ProviderModelConfig[]
  provider_name: string
}

export interface DiscoveryPolicyResponse {
  readonly host_port_allowlist: readonly string[]
  block_private_ips: boolean
  entry_count: number
}

export interface AddAllowlistEntryRequest {
  host_port: string
}

export interface RemoveAllowlistEntryRequest {
  host_port: string
}

// ── Messages ─────────────────────────────────────────────────

export type MessageType =
  | 'task_update'
  | 'question'
  | 'announcement'
  | 'review_request'
  | 'approval'
  | 'delegation'
  | 'status_report'
  | 'escalation'
  | 'meeting_contribution'
  | 'hr_notification'

export type MessagePriority = 'low' | 'normal' | 'high' | 'urgent'

export type AttachmentType = 'artifact' | 'file' | 'link'

export interface Attachment {
  type: AttachmentType
  ref: string
}

export interface MessageMetadata {
  task_id: string | null
  project_id: string | null
  tokens_used: number | null
  cost_usd: number | null
  readonly extra: readonly [string, string][]
}

export interface Message {
  id: string
  timestamp: string
  sender: string
  to: string
  type: MessageType
  priority: MessagePriority
  channel: string
  content: string
  readonly attachments: readonly Attachment[]
  metadata: MessageMetadata
}

export type ChannelType = 'topic' | 'direct' | 'broadcast'

export interface Channel {
  name: string
  type: ChannelType
  readonly subscribers: readonly string[]
}

// ── Health ───────────────────────────────────────────────────

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'down'
  persistence: boolean | null
  message_bus: boolean | null
  version: string
  uptime_seconds: number
}

// ── Autonomy ─────────────────────────────────────────────────

export interface AutonomyLevelResponse {
  agent_id: string
  level: AutonomyLevel
  promotion_pending: boolean
}

export interface AutonomyLevelRequest {
  level: AutonomyLevel
}

// ── Meetings ─────────────────────────────────────────────────

export type MeetingStatus =
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'budget_exhausted'

export const MEETING_STATUS_VALUES = [
  'scheduled', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exhausted',
] as const satisfies readonly MeetingStatus[]

export type MeetingProtocolType =
  | 'round_robin'
  | 'position_papers'
  | 'structured_phases'

export interface MeetingAgendaItem {
  title: string
  description: string
  presenter_id: string | null
}

export interface MeetingAgenda {
  title: string
  context: string
  readonly items: readonly MeetingAgendaItem[]
}

export type MeetingPhase =
  | 'agenda_broadcast'
  | 'round_robin_turn'
  | 'position_paper'
  | 'input_gathering'
  | 'discussion'
  | 'synthesis'
  | 'summary'

export interface MeetingContribution {
  agent_id: string
  content: string
  phase: MeetingPhase
  turn_number: number
  input_tokens: number
  output_tokens: number
  timestamp: string
}

export interface ActionItem {
  description: string
  assignee_id: string | null
  priority: Priority
}

export interface MeetingMinutes {
  meeting_id: string
  protocol_type: MeetingProtocolType
  leader_id: string
  readonly participant_ids: readonly string[]
  agenda: MeetingAgenda
  readonly contributions: readonly MeetingContribution[]
  summary: string
  readonly decisions: readonly string[]
  readonly action_items: readonly ActionItem[]
  conflicts_detected: boolean
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  started_at: string
  ended_at: string
}

export interface MeetingRecord {
  meeting_id: string
  meeting_type_name: string
  protocol_type: MeetingProtocolType
  status: MeetingStatus
  minutes: MeetingMinutes | null
  error_message: string | null
  token_budget: number
}

export interface MeetingResponse extends MeetingRecord {
  token_usage_by_participant: Record<string, number>
  contribution_rank: readonly string[]
  meeting_duration_seconds: number | null
}

export interface MeetingFilters {
  status?: MeetingStatus
  meeting_type?: string
  offset?: number
  limit?: number
}

export interface TriggerMeetingRequest {
  event_name: string
  context?: Record<string, string | string[]>
}

// ── Artifacts ───────────────────────────────────────────────

export interface Artifact {
  id: string
  type: ArtifactType
  path: string
  task_id: string
  created_by: string
  description: string
  project_id: string | null
  content_type: string
  size_bytes: number
  created_at: string | null
}

export interface CreateArtifactRequest {
  type: ArtifactType
  path: string
  task_id: string
  created_by: string
  description?: string
  content_type?: string
  project_id?: string | null
}

export interface ArtifactFilters {
  task_id?: string
  created_by?: string
  type?: ArtifactType
  project_id?: string
  offset?: number
  limit?: number
}

// ── Projects ────────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  description: string
  team: readonly string[]
  lead: string | null
  task_ids: readonly string[]
  deadline: string | null
  budget: number
  status: ProjectStatus
}

export interface CreateProjectRequest {
  name: string
  description?: string
  team?: string[]
  lead?: string | null
  deadline?: string
  budget?: number
}

export interface ProjectFilters {
  status?: ProjectStatus
  lead?: string
  offset?: number
  limit?: number
}

// ── WebSocket ────────────────────────────────────────────────

/** All valid WebSocket channel names. Runtime set derived from this in websocket store. */
export const WS_CHANNELS = ['tasks', 'agents', 'budget', 'messages', 'system', 'approvals', 'meetings', 'artifacts', 'projects'] as const

export type WsChannel = typeof WS_CHANNELS[number]

export type WsEventType =
  | 'task.created'
  | 'task.updated'
  | 'task.status_changed'
  | 'task.assigned'
  | 'agent.hired'
  | 'agent.fired'
  | 'agent.status_changed'
  | 'budget.record_added'
  | 'budget.alert'
  | 'message.sent'
  | 'system.error'
  | 'system.startup'
  | 'system.shutdown'
  | 'approval.submitted'
  | 'approval.approved'
  | 'approval.rejected'
  | 'approval.expired'
  | 'meeting.started'
  | 'meeting.completed'
  | 'meeting.failed'
  | 'coordination.started'
  | 'coordination.phase_completed'
  | 'coordination.completed'
  | 'coordination.failed'
  | 'artifact.created'
  | 'artifact.deleted'
  | 'artifact.content_uploaded'
  | 'project.created'
  | 'project.status_changed'

export const WS_EVENT_TYPE_VALUES = [
  'task.created', 'task.updated', 'task.status_changed', 'task.assigned',
  'agent.hired', 'agent.fired', 'agent.status_changed',
  'budget.record_added', 'budget.alert',
  'message.sent',
  'system.error', 'system.startup', 'system.shutdown',
  'approval.submitted', 'approval.approved', 'approval.rejected', 'approval.expired',
  'meeting.started', 'meeting.completed', 'meeting.failed',
  'coordination.started', 'coordination.phase_completed', 'coordination.completed', 'coordination.failed',
  'artifact.created', 'artifact.deleted', 'artifact.content_uploaded',
  'project.created', 'project.status_changed',
] as const satisfies readonly WsEventType[]

export const DEPARTMENT_NAME_VALUES = [
  'executive', 'product', 'design', 'engineering', 'quality_assurance',
  'data_analytics', 'operations', 'creative_marketing', 'security',
] as const satisfies readonly DepartmentName[]

export interface WsEvent {
  event_type: WsEventType
  channel: WsChannel
  timestamp: string
  payload: Record<string, unknown>
}

/** Filters for WebSocket channel subscriptions. */
export type WsSubscriptionFilters = Readonly<Record<string, string>>

export interface WsSubscribeMessage {
  action: 'subscribe'
  readonly channels: readonly WsChannel[]
  filters?: WsSubscriptionFilters
}

export interface WsUnsubscribeMessage {
  action: 'unsubscribe'
  readonly channels: readonly WsChannel[]
}

export interface WsAckMessage {
  action: 'subscribed' | 'unsubscribed'
  readonly channels: readonly WsChannel[]
}

export interface WsErrorMessage {
  error: string
}

// ── Event handler type ──────────────────────────────────────

export type WsEventHandler = (event: WsEvent) => void

// ── Collaboration scoring ────────────────────────────────────

export interface CollaborationScoreResult {
  score: number
  strategy_name: string
  readonly component_scores: readonly [string, number][]
  confidence: number
  override_active: boolean
}

export interface SetOverrideRequest {
  score: number
  reason: string
  expires_in_days?: number | null
}

export interface OverrideResponse {
  agent_id: string
  score: number
  reason: string
  applied_by: string
  applied_at: string
  expires_at: string | null
}

export interface LlmCalibrationRecord {
  id: string
  agent_id: string
  sampled_at: string
  interaction_record_id: string
  llm_score: number
  behavioral_score: number
  drift: number
  rationale: string
  model_used: string
  cost_usd: number
}

export interface CalibrationSummaryResponse {
  agent_id: string
  average_drift: number | null
  readonly records: readonly LlmCalibrationRecord[]
  record_count: number
}

// ── Coordination ─────────────────────────────────────────────

export interface CoordinateTaskRequest {
  agent_names?: string[] | null
  max_subtasks?: number
  max_concurrency_per_wave?: number | null
  fail_fast?: boolean | null
}

export interface CoordinationPhaseResponse {
  phase: string
  success: boolean
  duration_seconds: number
  error: string | null
}

export interface CoordinationResultResponse {
  parent_task_id: string
  topology: CoordinationTopology
  total_duration_seconds: number
  total_cost_usd: number
  readonly phases: readonly CoordinationPhaseResponse[]
  wave_count: number
  is_success: boolean
}

// ── Backup ───────────────────────────────────────────────────

export type BackupTrigger = 'scheduled' | 'manual' | 'shutdown' | 'startup' | 'pre_migration'

export type BackupComponent = 'persistence' | 'memory' | 'config'

export interface BackupManifest {
  synthorg_version: string
  timestamp: string
  trigger: BackupTrigger
  readonly components: readonly BackupComponent[]
  size_bytes: number
  checksum: string
  backup_id: string
}

export interface BackupInfo {
  backup_id: string
  timestamp: string
  trigger: BackupTrigger
  readonly components: readonly BackupComponent[]
  size_bytes: number
  compressed: boolean
}

export interface RestoreRequest {
  backup_id: string
  components?: BackupComponent[] | null
  confirm: boolean
}

export interface RestoreResponse {
  manifest: BackupManifest
  readonly restored_components: readonly BackupComponent[]
  safety_backup_id: string
  restart_required: boolean
}

// ── Pagination helpers ───────────────────────────────────────

export interface PaginationParams {
  offset?: number
  limit?: number
}

// ── Setup ───────────────────────────────────────────────────

export interface SetupStatusResponse {
  needs_admin: boolean
  needs_setup: boolean
  has_providers: boolean
  has_name_locales: boolean
  has_company: boolean
  has_agents: boolean
  min_password_length: number
}

export interface DiscoverModelsRequest {
  preset_hint?: string
}

export type SkillPattern =
  | 'tool_wrapper'
  | 'generator'
  | 'reviewer'
  | 'inversion'
  | 'pipeline'

export interface TemplateVariable {
  readonly name: string
  readonly description: string
  readonly var_type: string
  readonly default: string | number | boolean | null
  readonly required: boolean
}

export interface TemplateInfoResponse {
  name: string
  display_name: string
  description: string
  source: 'builtin' | 'user'
  tags: readonly string[]
  skill_patterns: readonly SkillPattern[]
  variables: readonly TemplateVariable[]
  agent_count: number
  department_count: number
  autonomy_level: string
  workflow: string
}

export interface SetupCompanyRequest {
  company_name: string
  description: string | null
  template_name: string | null
}

export interface SetupAgentRequest {
  name: string
  role: string
  level: SeniorityLevel
  personality_preset: string
  model_provider: string
  model_id: string
  department: string
  budget_limit_monthly: number | null
}

export interface SetupAgentSummary {
  name: string
  role: string
  department: string
  level: SeniorityLevel | null
  model_provider: string | null
  model_id: string | null
  tier: string
  personality_preset: string | null
}

export interface SetupCompanyResponse {
  company_name: string
  description: string | null
  template_applied: string | null
  department_count: number
  agent_count: number
  readonly agents: readonly SetupAgentSummary[]
}

export interface SetupAgentResponse {
  name: string
  role: string
  department: string
  model_provider: string
  model_id: string
}

export interface UpdateAgentModelRequest {
  model_provider: string
  model_id: string
}

export interface UpdateAgentNameRequest {
  name: string
}

export interface UpdateAgentPersonalityRequest {
  personality_preset: string
}

export interface PersonalityPresetInfo {
  readonly name: string
  readonly description: string
}

export interface PersonalityPresetsListResponse {
  readonly presets: readonly PersonalityPresetInfo[]
}

export interface SetupAgentsListResponse {
  readonly agents: readonly SetupAgentSummary[]
  agent_count: number
}

export interface SetupNameLocalesRequest {
  locales: string[]
}

export interface SetupNameLocalesResponse {
  readonly locales: readonly string[]
}

export interface AvailableLocalesResponse {
  readonly regions: Readonly<Record<string, readonly string[]>>
  readonly display_names: Readonly<Record<string, string>>
}

// ── Settings ────────────────────────────────────────────────

export type SettingNamespace =
  | 'api'
  | 'company'
  | 'providers'
  | 'memory'
  | 'budget'
  | 'security'
  | 'coordination'
  | 'observability'
  | 'backup'

export type SettingType = 'str' | 'int' | 'float' | 'bool' | 'enum' | 'json'

export type SettingLevel = 'basic' | 'advanced'

export type SettingSource = 'db' | 'env' | 'yaml' | 'default'

export interface SettingDefinition {
  namespace: SettingNamespace
  key: string
  type: SettingType
  default: string | null
  description: string
  group: string
  level: SettingLevel
  sensitive: boolean
  restart_required: boolean
  enum_values: readonly string[]
  validator_pattern: string | null
  min_value: number | null
  max_value: number | null
  yaml_path: string | null
}

export interface SettingEntry {
  definition: SettingDefinition
  value: string
  source: SettingSource
  updated_at: string | null
}

/** Backend enforces max_length=8192 on value. */
export interface UpdateSettingRequest {
  value: string
}

// ── Sink configuration ──────────────────────────────────────

export interface SinkRotation {
  strategy: 'builtin' | 'external'
  max_bytes: number
  backup_count: number
}

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

export interface SinkInfo {
  identifier: string
  sink_type: 'console' | 'file'
  level: LogLevel
  json_format: boolean
  rotation: SinkRotation | null
  is_default: boolean
  enabled: boolean
  routing_prefixes: readonly string[]
}

export interface TestSinkResult {
  valid: boolean
  error: string | null
}

// ── Company Config (parsed from settings JSON) ────────────

export interface AgentConfigEntry {
  name: string
  role: string
  department: string
  level: SeniorityLevel
  personality?: Record<string, unknown>
  model?: Record<string, unknown>
  memory?: Record<string, unknown>
  tools?: Record<string, unknown>
  authority?: Record<string, unknown>
  autonomy_level?: AutonomyLevel | null
}

export interface DepartmentTeam {
  readonly name: string
  readonly lead?: string
  readonly members?: readonly string[]
}

export interface DepartmentReportingLine {
  readonly subordinate: string
  readonly supervisor: string
  readonly subordinate_id?: string | null
  readonly supervisor_id?: string | null
}

export interface DepartmentEntry {
  readonly name: string
  readonly head?: string
  readonly head_id?: string | null
  readonly budget_percent?: number
  readonly teams?: readonly DepartmentTeam[]
  readonly reporting_lines?: readonly DepartmentReportingLine[]
  readonly autonomy_level?: AutonomyLevel | null
  readonly policies?: Record<string, unknown>
}

// ── Template Packs ──────────────────────────────────────────

export interface PackInfoResponse {
  readonly name: string
  readonly display_name: string
  readonly description: string
  readonly source: 'builtin' | 'user'
  readonly tags: readonly string[]
  readonly agent_count: number
  readonly department_count: number
}

export interface ApplyTemplatePackRequest {
  readonly pack_name: string
}

export interface ApplyTemplatePackResponse {
  readonly pack_name: string
  readonly agents_added: number
  readonly departments_added: number
}

// ── Workflow Definitions ───────────────────────────────────────

export type WorkflowNodeType =
  | 'start'
  | 'end'
  | 'task'
  | 'agent_assignment'
  | 'conditional'
  | 'parallel_split'
  | 'parallel_join'

export type WorkflowEdgeType =
  | 'sequential'
  | 'conditional_true'
  | 'conditional_false'
  | 'parallel_branch'

export interface WorkflowNodeData {
  readonly id: string
  readonly type: WorkflowNodeType
  readonly label: string
  readonly position_x: number
  readonly position_y: number
  readonly config: Record<string, unknown>
}

export interface WorkflowEdgeData {
  readonly id: string
  readonly source_node_id: string
  readonly target_node_id: string
  readonly type: WorkflowEdgeType
  readonly label: string | null
}

export interface WorkflowDefinition {
  readonly id: string
  readonly name: string
  readonly description: string
  readonly workflow_type: string
  readonly nodes: readonly WorkflowNodeData[]
  readonly edges: readonly WorkflowEdgeData[]
  readonly created_by: string
  readonly created_at: string
  readonly updated_at: string
  readonly version: number
}

export interface CreateWorkflowDefinitionRequest {
  readonly name: string
  readonly description?: string
  readonly workflow_type: string
  readonly nodes: readonly Record<string, unknown>[]
  readonly edges: readonly Record<string, unknown>[]
}

export interface UpdateWorkflowDefinitionRequest {
  readonly name?: string
  readonly description?: string
  readonly workflow_type?: string
  readonly nodes?: readonly Record<string, unknown>[]
  readonly edges?: readonly Record<string, unknown>[]
  readonly expected_version?: number
}

export interface WorkflowValidationError {
  readonly code: string
  readonly message: string
  readonly node_id: string | null
  readonly edge_id: string | null
}

export interface WorkflowValidationResult {
  readonly valid: boolean
  readonly errors: readonly WorkflowValidationError[]
}
