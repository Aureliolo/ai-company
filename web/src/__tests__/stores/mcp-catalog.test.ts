import type { McpCatalogEntry } from '@/api/types'
import { useMcpCatalogStore } from '@/stores/mcp-catalog'

vi.mock('@/api/endpoints/mcp-catalog', () => ({
  browseMcpCatalog: vi.fn(),
  searchMcpCatalog: vi.fn(),
  installMcpServer: vi.fn(),
  uninstallMcpServer: vi.fn(),
}))

const {
  browseMcpCatalog,
  installMcpServer,
  uninstallMcpServer,
} = await import('@/api/endpoints/mcp-catalog')

const githubEntry: McpCatalogEntry = {
  id: 'github-mcp',
  name: 'GitHub',
  description: 'desc',
  npm_package: '@modelcontextprotocol/server-github',
  required_connection_type: 'github',
  transport: 'stdio',
  capabilities: ['repository_access', 'issue_management'],
  tags: ['vcs'],
}

const filesystemEntry: McpCatalogEntry = {
  id: 'filesystem-mcp',
  name: 'Filesystem',
  description: 'desc',
  npm_package: '@modelcontextprotocol/server-filesystem',
  required_connection_type: null,
  transport: 'stdio',
  capabilities: ['file_read'],
  tags: ['local'],
}

describe('useMcpCatalogStore', () => {
  beforeEach(() => {
    useMcpCatalogStore.getState().reset()
    vi.clearAllMocks()
  })

  it('loads the catalog on fetchCatalog', async () => {
    vi.mocked(browseMcpCatalog).mockResolvedValue([githubEntry, filesystemEntry])
    await useMcpCatalogStore.getState().fetchCatalog()
    expect(useMcpCatalogStore.getState().entries).toHaveLength(2)
  })

  it('startInstall moves the wizard to picking-connection for entries that need one', () => {
    useMcpCatalogStore.setState({ entries: [githubEntry] })
    useMcpCatalogStore.getState().startInstall('github-mcp')
    expect(useMcpCatalogStore.getState().installFlow).toBe('picking-connection')
    expect(useMcpCatalogStore.getState().installContext.entryId).toBe('github-mcp')
  })

  it('startInstall skips straight to installing for connectionless entries', () => {
    useMcpCatalogStore.setState({ entries: [filesystemEntry] })
    useMcpCatalogStore.getState().startInstall('filesystem-mcp')
    expect(useMcpCatalogStore.getState().installFlow).toBe('installing')
  })

  it('confirmInstall transitions to done on success and remembers the entry', async () => {
    useMcpCatalogStore.setState({ entries: [filesystemEntry] })
    useMcpCatalogStore.getState().startInstall('filesystem-mcp')
    vi.mocked(installMcpServer).mockResolvedValue({
      status: 'installed',
      server_name: 'Filesystem',
      catalog_entry_id: 'filesystem-mcp',
      tool_count: 1,
    })

    await useMcpCatalogStore.getState().confirmInstall()

    const state = useMcpCatalogStore.getState()
    expect(state.installFlow).toBe('done')
    expect(state.installedEntryIds.has('filesystem-mcp')).toBe(true)
  })

  it('confirmInstall transitions to error on failure', async () => {
    useMcpCatalogStore.setState({ entries: [filesystemEntry] })
    useMcpCatalogStore.getState().startInstall('filesystem-mcp')
    vi.mocked(installMcpServer).mockRejectedValue(new Error('no connection'))

    await useMcpCatalogStore.getState().confirmInstall()

    const state = useMcpCatalogStore.getState()
    expect(state.installFlow).toBe('error')
    expect(state.installContext.errorMessage).toBe('no connection')
  })

  it('uninstall clears the installed marker on success', async () => {
    useMcpCatalogStore.setState({
      installedEntryIds: new Set(['github-mcp']),
    })
    vi.mocked(uninstallMcpServer).mockResolvedValue(undefined)

    const result = await useMcpCatalogStore
      .getState()
      .uninstall('github-mcp')

    expect(result).toBe(true)
    expect(useMcpCatalogStore.getState().installedEntryIds.has('github-mcp')).toBe(false)
  })

  it('resetInstall returns the wizard to idle', () => {
    useMcpCatalogStore.setState({ entries: [filesystemEntry] })
    useMcpCatalogStore.getState().startInstall('filesystem-mcp')
    useMcpCatalogStore.getState().resetInstall()
    expect(useMcpCatalogStore.getState().installFlow).toBe('idle')
  })
})
