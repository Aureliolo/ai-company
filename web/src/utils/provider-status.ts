import type { AgentRuntimeStatus } from '@/lib/utils'
import type { ProviderConfig } from '@/api/types'

/** Derive provider status from auth type and credential indicators. */
export function getProviderStatus(config: ProviderConfig): AgentRuntimeStatus {
  if (config.auth_type === 'none') return 'idle'
  if (config.auth_type === 'api_key') return config.has_api_key ? 'idle' : 'error'
  if (config.auth_type === 'oauth') return config.has_oauth_credentials ? 'idle' : 'error'
  if (config.auth_type === 'custom_header') return config.has_custom_header ? 'idle' : 'error'
  return config.has_api_key ? 'idle' : 'error'
}
