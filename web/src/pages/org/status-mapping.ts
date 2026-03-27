import type { AgentStatus } from '@/api/types'
import type { AgentRuntimeStatus } from '@/lib/utils'

/**
 * Map HR (administrative) agent status to an initial runtime status.
 * The runtime status may later be overridden by WebSocket events.
 */
export function mapHrToRuntime(hrStatus: AgentStatus): AgentRuntimeStatus {
  switch (hrStatus) {
    case 'terminated':
    case 'on_leave':
      return 'offline'
    case 'onboarding':
      return 'idle'
    case 'active':
      return 'idle'
  }
}

/**
 * Resolve the effective runtime status for an agent.
 * WebSocket-pushed runtime status takes precedence over the HR-derived default.
 */
export function resolveRuntimeStatus(
  agentId: string,
  hrStatus: AgentStatus,
  runtimeMap: Record<string, AgentRuntimeStatus>,
): AgentRuntimeStatus {
  return runtimeMap[agentId] ?? mapHrToRuntime(hrStatus)
}
