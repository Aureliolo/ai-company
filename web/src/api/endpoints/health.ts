import { apiClient, unwrap } from '../client'
import type { ApiResponse } from '../types/http'
import type {
  HealthStatus,
  LivenessStatus,
  ReadinessStatus,
} from '../types/system'

/**
 * Liveness probe -- always returns 200 while the backend process is
 * alive. Used by supervisors to decide whether to restart the pod.
 */
export async function getLiveness(): Promise<LivenessStatus> {
  const response = await apiClient.get<ApiResponse<LivenessStatus>>('/healthz')
  return unwrap(response)
}

/**
 * Readiness probe -- returns 200 when persistence + message bus are
 * healthy, 503 otherwise. Used by load-balancers to gate traffic.
 */
export async function getReadiness(): Promise<ReadinessStatus> {
  const response = await apiClient.get<ApiResponse<ReadinessStatus>>('/readyz')
  return unwrap(response)
}

/**
 * Legacy alias. Dashboard callers that still want the combined
 * signal (`persistence` / `message_bus` flags + binary status) should
 * migrate to :func:`getReadiness` -- this wrapper just forwards to
 * it so the old call-site shape keeps working.
 */
export async function getHealth(): Promise<HealthStatus> {
  return getReadiness()
}
