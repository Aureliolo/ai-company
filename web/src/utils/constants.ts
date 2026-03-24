/** Application-wide constants. */

import type { SettingNamespace, TaskStatus } from '@/api/types'

export const APP_NAME = 'SynthOrg'

export const WS_RECONNECT_BASE_DELAY = 1000
export const WS_RECONNECT_MAX_DELAY = 30000
export const WS_MAX_RECONNECT_ATTEMPTS = 20
/** Max incoming WS message size (bytes). Distinct from backend's 4 KiB client-message cap. */
export const WS_MAX_MESSAGE_SIZE = 131072

export const HEALTH_POLL_INTERVAL = 15000

export const DEFAULT_PAGE_SIZE = 50
export const MAX_PAGE_SIZE = 200

export const MIN_PASSWORD_LENGTH = 12

export const LOGIN_MAX_ATTEMPTS = 5
export const LOGIN_LOCKOUT_MS = 60_000

/** Ordered task statuses for Kanban columns. */
export const TASK_STATUS_ORDER: readonly TaskStatus[] = [
  'created',
  'assigned',
  'in_progress',
  'in_review',
  'blocked',
  'completed',
  'failed',
  'interrupted',
  'cancelled',
] as const

/** Terminal task statuses that cannot transition further. */
export const TERMINAL_STATUSES: ReadonlySet<TaskStatus> = new Set<TaskStatus>(['completed', 'cancelled'])

/** Task status transitions map. */
export const VALID_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  created: ['assigned'],
  assigned: ['in_progress', 'blocked', 'cancelled', 'failed', 'interrupted'],
  in_progress: ['in_review', 'blocked', 'cancelled', 'failed', 'interrupted'],
  in_review: ['completed', 'in_progress', 'blocked', 'cancelled'],
  blocked: ['assigned'],
  failed: ['assigned'],
  interrupted: ['assigned'],
  completed: [],
  cancelled: [],
}

/** Write-capable human roles. */
export const WRITE_ROLES = ['ceo', 'manager', 'board_member', 'pair_programmer'] as const

// ── Settings ────────────────────────────────────────────────

/** localStorage key for the basic/advanced toggle state. */
export const SETTINGS_ADVANCED_KEY = 'settings_show_advanced'

/** Display order for setting namespaces shown in the Settings page.
 * 'company' and 'providers' are excluded -- they have dedicated pages. */
export const NAMESPACE_ORDER: readonly SettingNamespace[] = [
  'api',
  'memory',
  'budget',
  'security',
  'coordination',
  'observability',
  'backup',
] as const

/** Human-readable display names for setting namespaces. */
export const NAMESPACE_DISPLAY_NAMES: Readonly<Record<SettingNamespace, string>> = {
  api: 'API',
  company: 'Company',
  providers: 'Providers',
  memory: 'Memory',
  budget: 'Budget',
  security: 'Security',
  coordination: 'Coordination',
  observability: 'Observability',
  backup: 'Backup',
}

/** sessionStorage key for the advanced-mode first-toggle warning. */
export const SETTINGS_ADVANCED_WARNED_KEY = 'settings_advanced_warned'

/** Settings that should never be shown in the GUI (internal/system-managed). */
const HIDDEN_SETTING_KEYS = ['api/setup_complete'] as const
export const HIDDEN_SETTINGS: ReadonlySet<string> = new Set(HIDDEN_SETTING_KEYS)

/**
 * Settings that carry elevated security risk when misconfigured.
 * The GUI shows an additional warning for these keys.
 */
const SECURITY_SENSITIVE_KEYS = ['api/auth_exclude_paths'] as const
export const SECURITY_SENSITIVE_SETTINGS: ReadonlySet<string> = new Set(SECURITY_SENSITIVE_KEYS)

/** Settings that are simple string arrays and should render as chip inputs in GUI mode. */
export const SIMPLE_ARRAY_SETTINGS: ReadonlySet<string> = new Set([
  'api/cors_allowed_origins',
  'api/rate_limit_exclude_paths',
  'api/auth_exclude_paths',
])
