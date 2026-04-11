import { http, HttpResponse } from 'msw'
import type {
  Connection,
  HealthReport,
  McpCatalogEntry,
  OauthInitiateResponse,
  OauthTokenStatus,
  TunnelStatus,
} from '@/api/types'
import { apiError, apiSuccess } from './helpers'

const NOW = '2026-04-11T12:00:00Z'

const mockConnections: Connection[] = [
  {
    id: 'conn-000000000001',
    name: 'primary-github',
    connection_type: 'github',
    auth_method: 'bearer_token',
    base_url: 'https://api.github.com',
    health_check_enabled: true,
    health_status: 'healthy',
    last_health_check_at: NOW,
    metadata: {},
    created_at: '2026-04-01T09:00:00Z',
    updated_at: NOW,
  },
  {
    id: 'conn-000000000002',
    name: 'dev-slack',
    connection_type: 'slack',
    auth_method: 'bearer_token',
    base_url: null,
    health_check_enabled: true,
    health_status: 'degraded',
    last_health_check_at: NOW,
    metadata: {},
    created_at: '2026-04-02T10:30:00Z',
    updated_at: NOW,
  },
  {
    id: 'conn-000000000003',
    name: 'ops-smtp',
    connection_type: 'smtp',
    auth_method: 'basic_auth',
    base_url: null,
    health_check_enabled: true,
    health_status: 'unhealthy',
    last_health_check_at: NOW,
    metadata: {},
    created_at: '2026-04-03T11:15:00Z',
    updated_at: NOW,
  },
  {
    id: 'conn-000000000004',
    name: 'reporting-db',
    connection_type: 'database',
    auth_method: 'basic_auth',
    base_url: null,
    health_check_enabled: true,
    health_status: 'healthy',
    last_health_check_at: NOW,
    metadata: {},
    created_at: '2026-04-04T08:00:00Z',
    updated_at: NOW,
  },
  {
    id: 'conn-000000000005',
    name: 'billing-api',
    connection_type: 'generic_http',
    auth_method: 'api_key',
    base_url: 'https://billing.example.com',
    health_check_enabled: true,
    health_status: 'unknown',
    last_health_check_at: null,
    metadata: {},
    created_at: '2026-04-05T14:20:00Z',
    updated_at: NOW,
  },
  {
    id: 'conn-000000000006',
    name: 'gh-oauth-app',
    connection_type: 'oauth_app',
    auth_method: 'oauth2',
    base_url: null,
    health_check_enabled: false,
    health_status: 'unknown',
    last_health_check_at: null,
    metadata: {},
    created_at: '2026-04-06T09:45:00Z',
    updated_at: NOW,
  },
]

const mockHealthReports: HealthReport[] = mockConnections.map((conn) => ({
  connection_name: conn.name,
  status: conn.health_status,
  latency_ms: conn.health_status === 'healthy' ? 42 : null,
  error_detail: conn.health_status === 'unhealthy' ? 'Connection refused' : null,
  checked_at: NOW,
  consecutive_failures: conn.health_status === 'unhealthy' ? 4 : 0,
}))

const mockCatalogEntries: McpCatalogEntry[] = [
  {
    id: 'github-mcp',
    name: 'GitHub',
    description: 'Read and write GitHub repositories, issues, pull requests, and actions',
    npm_package: '@modelcontextprotocol/server-github',
    required_connection_type: 'github',
    transport: 'stdio',
    capabilities: ['repository_access', 'issue_management', 'pull_requests', 'actions'],
    tags: ['vcs', 'collaboration', 'ci'],
  },
  {
    id: 'slack-mcp',
    name: 'Slack',
    description: 'Send and receive Slack messages, manage channels and users',
    npm_package: '@modelcontextprotocol/server-slack',
    required_connection_type: 'slack',
    transport: 'stdio',
    capabilities: ['messaging', 'channel_management', 'user_lookup'],
    tags: ['communication', 'team'],
  },
  {
    id: 'filesystem-mcp',
    name: 'Filesystem',
    description: 'Read, write, and manage files on the local filesystem',
    npm_package: '@modelcontextprotocol/server-filesystem',
    required_connection_type: null,
    transport: 'stdio',
    capabilities: ['file_read', 'file_write', 'directory_listing'],
    tags: ['filesystem', 'local'],
  },
  {
    id: 'postgres-mcp',
    name: 'PostgreSQL',
    description: 'Query and manage PostgreSQL databases',
    npm_package: '@modelcontextprotocol/server-postgres',
    required_connection_type: 'database',
    transport: 'stdio',
    capabilities: ['sql_query', 'schema_inspect', 'data_mutation'],
    tags: ['database', 'sql'],
  },
  {
    id: 'sqlite-mcp',
    name: 'SQLite',
    description: 'Query and manage SQLite databases',
    npm_package: '@modelcontextprotocol/server-sqlite',
    required_connection_type: 'database',
    transport: 'stdio',
    capabilities: ['sql_query', 'schema_inspect'],
    tags: ['database', 'sql', 'local'],
  },
  {
    id: 'brave-search-mcp',
    name: 'Brave Search',
    description: 'Web and local search via the Brave Search API',
    npm_package: '@modelcontextprotocol/server-brave-search',
    required_connection_type: 'generic_http',
    transport: 'stdio',
    capabilities: ['web_search', 'local_search'],
    tags: ['search', 'web'],
  },
  {
    id: 'puppeteer-mcp',
    name: 'Puppeteer',
    description: 'Browser automation for web scraping and testing',
    npm_package: '@modelcontextprotocol/server-puppeteer',
    required_connection_type: null,
    transport: 'stdio',
    capabilities: ['browser_automation', 'screenshot', 'navigation'],
    tags: ['browser', 'automation', 'testing'],
  },
  {
    id: 'memory-mcp',
    name: 'Memory',
    description: 'Persistent memory and knowledge graph for agents',
    npm_package: '@modelcontextprotocol/server-memory',
    required_connection_type: null,
    transport: 'stdio',
    capabilities: ['memory_store', 'memory_retrieve', 'knowledge_graph'],
    tags: ['memory', 'knowledge'],
  },
]

const tunnelState: { url: string | null } = { url: null }

export const connectionsList = [
  http.get('/api/v1/connections/', () => HttpResponse.json(apiSuccess(mockConnections))),
  http.get('/api/v1/connections/:name', ({ params }) => {
    const conn = mockConnections.find((c) => c.name === params.name)
    if (!conn) return HttpResponse.json(apiError('Connection not found'), { status: 404 })
    return HttpResponse.json(apiSuccess(conn))
  }),
  http.post('/api/v1/connections/', async ({ request }) => {
    const body = (await request.json()) as Partial<Connection> & { connection_type?: string }
    if (!body.name) {
      return HttpResponse.json(apiError("Field 'name' is required"), { status: 400 })
    }
    const created: Connection = {
      id: `conn-${String(body.name)}`,
      name: body.name as string,
      connection_type: (body.connection_type ?? 'github') as Connection['connection_type'],
      auth_method: 'api_key',
      base_url: null,
      health_check_enabled: true,
      health_status: 'unknown',
      last_health_check_at: null,
      metadata: {},
      created_at: NOW,
      updated_at: NOW,
    }
    return HttpResponse.json(apiSuccess(created), { status: 201 })
  }),
  http.patch('/api/v1/connections/:name', async ({ params }) => {
    const conn = mockConnections.find((c) => c.name === params.name)
    if (!conn) return HttpResponse.json(apiError('Connection not found'), { status: 404 })
    return HttpResponse.json(apiSuccess({ ...conn, updated_at: NOW }))
  }),
  http.delete('/api/v1/connections/:name', () => HttpResponse.json(apiSuccess(null))),
  http.get('/api/v1/connections/:name/health', ({ params }) => {
    const report = mockHealthReports.find((r) => r.connection_name === params.name)
    if (!report) return HttpResponse.json(apiError('Connection not found'), { status: 404 })
    return HttpResponse.json(apiSuccess(report))
  }),
  http.get('/api/v1/connections/:name/secrets/:field', ({ params }) =>
    HttpResponse.json(
      apiSuccess({ field: String(params.field), value: 'revealed-secret-value' }),
    ),
  ),
]

export const integrationHealthList = [
  http.get('/api/v1/integrations/health/', () => HttpResponse.json(apiSuccess(mockHealthReports))),
  http.get('/api/v1/integrations/health/:name', ({ params }) => {
    const report = mockHealthReports.find((r) => r.connection_name === params.name)
    if (!report) return HttpResponse.json(apiError('Connection not found'), { status: 404 })
    return HttpResponse.json(apiSuccess(report))
  }),
]

export const oauthHandlers = [
  http.post('/api/v1/oauth/initiate', () =>
    HttpResponse.json(
      apiSuccess<OauthInitiateResponse>({
        authorization_url: 'https://example.com/oauth/authorize?state=abc',
        state_token: 'mock-state-token-abc',
      }),
    ),
  ),
  http.get('/api/v1/oauth/status/:connectionName', ({ params }) =>
    HttpResponse.json(
      apiSuccess<OauthTokenStatus>({
        connection_name: String(params.connectionName),
        has_token: true,
        token_expires_at: '2026-05-11T12:00:00Z',
      }),
    ),
  ),
]

export const mcpCatalogHandlers = [
  http.get('/api/v1/integrations/mcp/catalog', () => HttpResponse.json(apiSuccess(mockCatalogEntries))),
  http.get('/api/v1/integrations/mcp/catalog/search', ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('q') ?? '').toLowerCase()
    const matches = mockCatalogEntries.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q)),
    )
    return HttpResponse.json(apiSuccess(matches))
  }),
  http.get('/api/v1/integrations/mcp/catalog/:entryId', ({ params }) => {
    const entry = mockCatalogEntries.find((e) => e.id === params.entryId)
    if (!entry) return HttpResponse.json(apiError('Catalog entry not found'), { status: 404 })
    return HttpResponse.json(apiSuccess(entry))
  }),
  http.post('/api/v1/integrations/mcp/catalog/install', async ({ request }) => {
    const body = (await request.json()) as { catalog_entry_id?: string; connection_name?: string }
    if (!body.catalog_entry_id) {
      return HttpResponse.json(apiError("Field 'catalog_entry_id' is required"), { status: 400 })
    }
    const entry = mockCatalogEntries.find((e) => e.id === body.catalog_entry_id)
    if (!entry) return HttpResponse.json(apiError('Catalog entry not found'), { status: 404 })
    return HttpResponse.json(
      apiSuccess({
        status: 'installed' as const,
        server_name: entry.name,
        catalog_entry_id: entry.id,
        tool_count: entry.capabilities.length,
      }),
    )
  }),
  http.delete('/api/v1/integrations/mcp/catalog/install/:entryId', () =>
    HttpResponse.json(apiSuccess(null)),
  ),
]

export const tunnelHandlers = [
  http.get('/api/v1/integrations/tunnel/status', () =>
    HttpResponse.json(apiSuccess<TunnelStatus>({ public_url: tunnelState.url })),
  ),
  http.post('/api/v1/integrations/tunnel/start', () => {
    tunnelState.url = 'https://mock-tunnel.ngrok.io'
    return HttpResponse.json(apiSuccess({ public_url: tunnelState.url }))
  }),
  http.post('/api/v1/integrations/tunnel/stop', () => {
    tunnelState.url = null
    return HttpResponse.json(apiSuccess(null))
  }),
]

export const emptyConnectionsList = [
  http.get('/api/v1/connections/', () => HttpResponse.json(apiSuccess([]))),
  http.get('/api/v1/integrations/health/', () => HttpResponse.json(apiSuccess([]))),
]

export const integrationsHandlers = [
  ...connectionsList,
  ...integrationHealthList,
  ...oauthHandlers,
  ...mcpCatalogHandlers,
  ...tunnelHandlers,
]
