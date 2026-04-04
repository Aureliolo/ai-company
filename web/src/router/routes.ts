/**
 * Route path constants -- single source of truth for all URL paths.
 *
 * Used by the router configuration, sidebar navigation, route guards,
 * and programmatic navigation throughout the dashboard.
 */
export const ROUTES = {
  DASHBOARD: '/',
  LOGIN: '/login',
  SETUP: '/setup',
  SETUP_STEP: '/setup/:step',
  ORG: '/org',
  ORG_EDIT: '/org/edit',
  TASKS: '/tasks',
  TASK_DETAIL: '/tasks/:taskId',
  BUDGET: '/budget',
  BUDGET_FORECAST: '/budget/forecast',
  APPROVALS: '/approvals',
  AGENTS: '/agents',
  AGENT_DETAIL: '/agents/:agentName',
  MESSAGES: '/messages',
  MEETINGS: '/meetings',
  MEETING_DETAIL: '/meetings/:meetingId',
  PROVIDERS: '/providers',
  PROVIDER_DETAIL: '/providers/:providerName',
  PROJECTS: '/projects',
  PROJECT_DETAIL: '/projects/:projectId',
  ARTIFACTS: '/artifacts',
  ARTIFACT_DETAIL: '/artifacts/:artifactId',
  WORKFLOWS: '/workflows',
  WORKFLOW_EDITOR: '/workflows/editor',
  SETTINGS: '/settings',
  SETTINGS_NAMESPACE: '/settings/:namespace',
  SETTINGS_SINKS: '/settings/observability/sinks',
  SETTINGS_CEREMONY_POLICY: '/settings/coordination/ceremony-policy',
  SETTINGS_FINE_TUNING: '/settings/memory/fine-tuning',
  DOCUMENTATION: '/docs/',
} as const

/** Routes accessible without authentication. */
export const PUBLIC_ROUTES: readonly string[] = [
  ROUTES.LOGIN,
  ROUTES.SETUP,
  ROUTES.SETUP_STEP,
]
