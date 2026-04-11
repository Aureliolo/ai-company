import type { Connection, HealthReport } from '@/api/types'
import { useConnectionsStore } from '@/stores/connections'

vi.mock('@/api/endpoints/connections', () => ({
  listConnections: vi.fn(),
  createConnection: vi.fn(),
  updateConnection: vi.fn(),
  deleteConnection: vi.fn(),
  checkConnectionHealth: vi.fn(),
}))

vi.mock('@/api/endpoints/integration-health', () => ({
  listIntegrationHealth: vi.fn(),
}))

const {
  listConnections,
  createConnection,
  deleteConnection,
  checkConnectionHealth,
} = await import('@/api/endpoints/connections')
const { listIntegrationHealth } = await import(
  '@/api/endpoints/integration-health'
)

const sampleConnection: Connection = {
  id: 'conn-primary-github',
  name: 'primary-github',
  connection_type: 'github',
  auth_method: 'bearer_token',
  base_url: 'https://api.github.com',
  health_check_enabled: true,
  health_status: 'healthy',
  last_health_check_at: '2026-04-12T08:00:00Z',
  metadata: {},
  created_at: '2026-04-01T09:00:00Z',
  updated_at: '2026-04-12T08:00:00Z',
}

const sampleReport: HealthReport = {
  connection_name: 'primary-github',
  status: 'healthy',
  latency_ms: 42,
  error_detail: null,
  checked_at: '2026-04-12T08:00:00Z',
  consecutive_failures: 0,
}

describe('useConnectionsStore', () => {
  beforeEach(() => {
    useConnectionsStore.getState().reset()
    vi.clearAllMocks()
  })

  it('fetches connections and merges health reports', async () => {
    vi.mocked(listConnections).mockResolvedValue([sampleConnection])
    vi.mocked(listIntegrationHealth).mockResolvedValue([sampleReport])

    await useConnectionsStore.getState().fetchConnections()

    const state = useConnectionsStore.getState()
    expect(state.connections).toHaveLength(1)
    expect(state.healthMap['primary-github']).toEqual(sampleReport)
    expect(state.listLoading).toBe(false)
  })

  it('records an error message when the list call fails', async () => {
    vi.mocked(listConnections).mockRejectedValue(new Error('Network down'))
    vi.mocked(listIntegrationHealth).mockResolvedValue([])

    await useConnectionsStore.getState().fetchConnections()

    expect(useConnectionsStore.getState().listError).toBe('Network down')
    expect(useConnectionsStore.getState().listLoading).toBe(false)
  })

  it('appends a new connection on create', async () => {
    vi.mocked(createConnection).mockResolvedValue(sampleConnection)

    const result = await useConnectionsStore.getState().createConnection({
      name: 'primary-github',
      connection_type: 'github',
      credentials: { token: 'abc' },
    })

    expect(result).toEqual(sampleConnection)
    expect(useConnectionsStore.getState().connections).toHaveLength(1)
  })

  it('optimistically removes a connection on delete and rolls back on failure', async () => {
    useConnectionsStore.setState({ connections: [sampleConnection] })
    vi.mocked(deleteConnection).mockRejectedValue(new Error('boom'))

    const result = await useConnectionsStore
      .getState()
      .deleteConnection('primary-github')

    expect(result).toBe(false)
    expect(useConnectionsStore.getState().connections).toHaveLength(1)
  })

  it('runs a health check and stores the latest report', async () => {
    vi.mocked(checkConnectionHealth).mockResolvedValue({
      ...sampleReport,
      status: 'degraded',
      latency_ms: 900,
    })

    await useConnectionsStore.getState().runHealthCheck('primary-github')

    expect(
      useConnectionsStore.getState().healthMap['primary-github']?.status,
    ).toBe('degraded')
    expect(useConnectionsStore.getState().checkingHealth).not.toContain(
      'primary-github',
    )
  })

  it('updates filters without touching list state', () => {
    useConnectionsStore.getState().setSearchQuery('github')
    useConnectionsStore.getState().setTypeFilter('github')
    useConnectionsStore.getState().setHealthFilter('healthy')

    const state = useConnectionsStore.getState()
    expect(state.searchQuery).toBe('github')
    expect(state.typeFilter).toBe('github')
    expect(state.healthFilter).toBe('healthy')
  })
})
