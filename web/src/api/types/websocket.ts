/** WebSocket event types, channels and subscription messages. */

export const WS_CHANNELS = ['tasks', 'agents', 'budget', 'messages', 'system', 'approvals', 'meetings', 'artifacts', 'projects', 'company', 'departments', 'scaling'] as const

export type WsChannel = typeof WS_CHANNELS[number]

export const WS_EVENT_TYPE_VALUES = [
  'task.created', 'task.updated', 'task.status_changed', 'task.assigned',
  'agent.hired', 'agent.fired', 'agent.status_changed',
  'personality.trimmed',
  'budget.record_added', 'budget.alert',
  'message.sent',
  'system.error', 'system.startup', 'system.shutdown',
  'approval.submitted', 'approval.approved', 'approval.rejected', 'approval.expired',
  'meeting.started', 'meeting.completed', 'meeting.failed',
  'coordination.started', 'coordination.phase_completed', 'coordination.completed', 'coordination.failed',
  'artifact.created', 'artifact.deleted', 'artifact.content_uploaded',
  'project.created', 'project.status_changed',
  'memory.fine_tune.progress', 'memory.fine_tune.stage_changed', 'memory.fine_tune.completed', 'memory.fine_tune.failed',
  'company.updated',
  'department.created', 'department.updated', 'department.deleted', 'departments.reordered',
  'agent.created', 'agent.updated', 'agent.deleted', 'agents.reordered',
  'hr.scaling.trigger_requested', 'hr.scaling.cycle_started', 'hr.scaling.cycle_complete',
  'hr.scaling.strategy_evaluated', 'hr.scaling.guard_applied', 'hr.scaling.executed',
  'hr.scaling.execution_failed', 'hr.scaling.decision_approved', 'hr.scaling.decision_rejected',
  'hr.scaling.manual_trigger_requested',
] as const

export type WsEventType = (typeof WS_EVENT_TYPE_VALUES)[number]

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

export type WsEventHandler = (event: WsEvent) => void
