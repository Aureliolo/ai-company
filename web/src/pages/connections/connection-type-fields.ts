import type { ConnectionType } from '@/api/types'

export interface ConnectionFieldSpec {
  readonly key: string
  readonly label: string
  readonly type: 'text' | 'password' | 'number' | 'url'
  readonly placeholder?: string
  readonly required: boolean
  readonly hint?: string
}

export interface ConnectionTypeSpec {
  readonly label: string
  readonly description: string
  readonly defaultAuthMethod: 'api_key' | 'oauth2' | 'basic_auth' | 'bearer_token' | 'custom'
  /** Top-level fields stored on the connection row (e.g. base_url). */
  readonly topLevelFields: readonly ConnectionFieldSpec[]
  /** Credential fields passed in `credentials: {}`. */
  readonly credentialFields: readonly ConnectionFieldSpec[]
}

export const CONNECTION_TYPE_FIELDS: Record<ConnectionType, ConnectionTypeSpec> = {
  github: {
    label: 'GitHub',
    description: 'Access GitHub repositories, issues, and pull requests.',
    defaultAuthMethod: 'bearer_token',
    topLevelFields: [
      {
        key: 'base_url',
        label: 'API URL',
        type: 'url',
        placeholder: 'https://api.github.com',
        required: false,
        hint: 'Leave blank for github.com',
      },
    ],
    credentialFields: [
      {
        key: 'token',
        label: 'Personal Access Token',
        type: 'password',
        required: true,
        placeholder: 'ghp_...',
      },
    ],
  },
  slack: {
    label: 'Slack',
    description: 'Send messages and manage channels via Slack.',
    defaultAuthMethod: 'bearer_token',
    topLevelFields: [],
    credentialFields: [
      {
        key: 'token',
        label: 'Bot Token',
        type: 'password',
        required: true,
        placeholder: 'xoxb-...',
      },
      {
        key: 'signing_secret',
        label: 'Signing Secret',
        type: 'password',
        required: true,
        hint: 'Used to verify inbound webhooks',
      },
    ],
  },
  smtp: {
    label: 'SMTP',
    description: 'Send outbound email via an SMTP server.',
    defaultAuthMethod: 'basic_auth',
    topLevelFields: [],
    credentialFields: [
      { key: 'host', label: 'Host', type: 'text', required: true, placeholder: 'smtp.example.com' },
      { key: 'port', label: 'Port', type: 'number', required: true, placeholder: '587' },
      { key: 'username', label: 'Username', type: 'text', required: true },
      { key: 'password', label: 'Password', type: 'password', required: true },
    ],
  },
  database: {
    label: 'Database',
    description: 'Connect to a SQL database (PostgreSQL, MySQL, SQLite).',
    defaultAuthMethod: 'basic_auth',
    topLevelFields: [],
    credentialFields: [
      {
        key: 'dialect',
        label: 'Dialect',
        type: 'text',
        required: true,
        placeholder: 'postgresql',
        hint: 'postgresql, mysql, or sqlite',
      },
      { key: 'host', label: 'Host', type: 'text', required: false, hint: 'Not required for SQLite' },
      { key: 'port', label: 'Port', type: 'number', required: false },
      { key: 'username', label: 'Username', type: 'text', required: false },
      { key: 'password', label: 'Password', type: 'password', required: false },
      { key: 'database', label: 'Database', type: 'text', required: true },
    ],
  },
  generic_http: {
    label: 'Generic HTTP',
    description: 'Any REST or HTTP API with an API key or bearer token.',
    defaultAuthMethod: 'api_key',
    topLevelFields: [
      {
        key: 'base_url',
        label: 'Base URL',
        type: 'url',
        required: true,
        placeholder: 'https://api.example.com',
      },
    ],
    credentialFields: [
      {
        key: 'token',
        label: 'API Key / Token',
        type: 'password',
        required: true,
      },
    ],
  },
  oauth_app: {
    label: 'OAuth App',
    description: 'Register OAuth client credentials for reuse across connections.',
    defaultAuthMethod: 'oauth2',
    topLevelFields: [],
    credentialFields: [
      { key: 'client_id', label: 'Client ID', type: 'text', required: true },
      { key: 'client_secret', label: 'Client Secret', type: 'password', required: true },
      { key: 'auth_url', label: 'Authorization URL', type: 'url', required: true },
      { key: 'token_url', label: 'Token URL', type: 'url', required: true },
    ],
  },
}

const DATABASE_SERVER_FIELDS = new Set(['host', 'port', 'username', 'password'])

/**
 * Validate a single connection field.
 *
 * For ``database`` type connections, pass the current ``dialect``
 * value so that host/port/username/password are required for
 * non-SQLite dialects (PostgreSQL, MySQL) but optional for SQLite.
 */
export function validateConnectionField(
  spec: ConnectionFieldSpec,
  value: string,
  dialect?: string,
): string | null {
  let effectiveRequired = spec.required
  if (
    !effectiveRequired &&
    DATABASE_SERVER_FIELDS.has(spec.key) &&
    dialect !== undefined &&
    dialect.toLowerCase() !== 'sqlite'
  ) {
    effectiveRequired = true
  }
  if (effectiveRequired && !value.trim()) {
    return `${spec.label} is required`
  }
  if (spec.type === 'url' && value.trim()) {
    try {
      const url = new URL(value)
      if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        return `${spec.label} must be an http(s) URL`
      }
    } catch {
      return `${spec.label} must be a valid URL`
    }
  }
  if (spec.type === 'number' && value.trim()) {
    const n = Number(value)
    if (!Number.isFinite(n)) {
      return `${spec.label} must be a number`
    }
  }
  return null
}

export function validateConnectionName(name: string): string | null {
  const trimmed = name.trim()
  if (!trimmed) return 'Name is required'
  if (!/^[a-z0-9_-]+$/i.test(trimmed)) {
    return 'Name may only contain letters, numbers, hyphens, and underscores'
  }
  return null
}
