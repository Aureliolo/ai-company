import type { AgentRuntimeStatus } from '@/lib/utils'
import type { AuthType, ProviderConfig } from '@/api/types/providers'

/** Derive provider status from auth type and credential indicators. */
export function getProviderStatus(config: ProviderConfig): AgentRuntimeStatus {
  const authType: AuthType = config.auth_type
  switch (authType) {
    case 'none':
      return 'idle'
    case 'api_key':
      return config.has_api_key ? 'idle' : 'error'
    case 'oauth':
      return config.has_oauth_credentials ? 'idle' : 'error'
    case 'custom_header':
      return config.has_custom_header ? 'idle' : 'error'
    case 'subscription':
      return config.has_subscription_token ? 'idle' : 'error'
    default: {
      const _exhaustive: never = authType
      return _exhaustive
    }
  }
}
