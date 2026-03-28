import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseSettingsDataReturn } from '@/hooks/useSettingsData'
import type { SettingEntry } from '@/api/types'

function makeSetting(overrides: Partial<SettingEntry['definition']> & { value?: string; source?: SettingEntry['source'] } = {}): SettingEntry {
  const {
    value = '3001',
    source = 'default',
    ...defOverrides
  } = overrides
  return {
    definition: {
      namespace: 'api',
      key: 'server_port',
      type: 'int',
      default: '3001',
      description: 'Server bind port',
      group: 'Server',
      level: 'basic',
      sensitive: false,
      restart_required: false,
      enum_values: [],
      validator_pattern: null,
      min_value: 1,
      max_value: 65535,
      yaml_path: 'api.server.port',
      ...defOverrides,
    },
    value,
    source,
    updated_at: null,
  }
}

const mockEntries: SettingEntry[] = [
  makeSetting(),
  makeSetting({
    key: 'rate_limit_max_requests',
    description: 'Maximum requests per time window',
    group: 'Rate Limiting',
    min_value: 1,
    max_value: 10000,
    value: '100',
  }),
  makeSetting({
    namespace: 'budget',
    key: 'total_monthly',
    type: 'float',
    description: 'Monthly budget limit',
    group: 'Limits',
    min_value: 0,
    max_value: null,
    yaml_path: 'budget.total_monthly',
    value: '100.0',
  }),
  makeSetting({
    namespace: 'security',
    key: 'enabled',
    type: 'bool',
    description: 'Master switch for the security subsystem',
    group: 'General',
    min_value: null,
    max_value: null,
    yaml_path: 'security.enabled',
    value: 'true',
  }),
  makeSetting({
    key: 'api_prefix',
    description: 'URL prefix for all API routes',
    group: 'Server',
    level: 'advanced',
    min_value: null,
    max_value: null,
    value: '/api/v1',
  }),
]

const mockUpdateSetting = vi.fn().mockResolvedValue({
  definition: { namespace: 'api', key: 'server_port', type: 'int', default: '3001', description: 'Server bind port', group: 'Server', level: 'basic', sensitive: false, restart_required: false, enum_values: [], validator_pattern: null, min_value: 1, max_value: 65535, yaml_path: 'api.server.port' },
  value: '3001', source: 'db', updated_at: null,
})
const mockResetSetting = vi.fn().mockResolvedValue(undefined)

const defaultHookReturn: UseSettingsDataReturn = {
  schema: [],
  entries: mockEntries,
  loading: false,
  error: null,
  saving: false,
  saveError: null,
  wsConnected: true,
  wsSetupError: null,
  updateSetting: mockUpdateSetting,
  resetSetting: mockResetSetting,
}

let hookReturn = { ...defaultHookReturn }

const getSettingsData = vi.fn(() => hookReturn)
// Dynamic key avoids Vitest's ESM mock hoisting from
// inlining the hook name, which breaks the spy reference
// to getSettingsData. See: useSettingsData + getSettingsData.
vi.mock('@/hooks/useSettingsData', () => {
  const hookName = 'useSettingsData'
  return { [hookName]: () => getSettingsData() }
})

// Mock the settings store for savingKeys
vi.mock('@/stores/settings', () => ({
  useSettingsStore: vi.fn((selector: (s: { savingKeys: ReadonlySet<string> }) => unknown) =>
    selector({ savingKeys: new Set() }),
  ),
}))

import SettingsPage from '@/pages/SettingsPage'

function renderSettings() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('SettingsPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('renders page heading', () => {
    renderSettings()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultHookReturn, loading: true, entries: [] }
    renderSettings()
    expect(screen.getByLabelText('Loading settings')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data already exists', () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    renderSettings()
    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.queryByLabelText('Loading settings')).not.toBeInTheDocument()
  })

  it('renders namespace sections', () => {
    renderSettings()
    expect(screen.getByText('API')).toBeInTheDocument()
    expect(screen.getByText('Budget')).toBeInTheDocument()
    expect(screen.getByText('Security')).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    renderSettings()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning when not connected', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    renderSettings()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })

  it('renders search input', () => {
    renderSettings()
    expect(screen.getByLabelText('Search settings')).toBeInTheDocument()
  })

  it('renders Advanced toggle', () => {
    renderSettings()
    expect(screen.getByText('Advanced')).toBeInTheDocument()
  })

  it('renders Code view toggle', () => {
    renderSettings()
    expect(screen.getByText('Code')).toBeInTheDocument()
  })

  it('hides advanced settings in basic mode', () => {
    renderSettings()
    // api_prefix is level=advanced, should not appear
    expect(screen.queryByText('Api Prefix')).not.toBeInTheDocument()
  })

  it('shows advanced settings when advanced mode is enabled', () => {
    localStorage.setItem('settings_show_advanced', 'true')
    renderSettings()
    expect(screen.getByText('Api Prefix')).toBeInTheDocument()
  })

  it('shows empty state when no entries match', () => {
    hookReturn = { ...defaultHookReturn, entries: [] }
    renderSettings()
    expect(screen.getByText('No settings available')).toBeInTheDocument()
  })

  it('shows custom wsSetupError message when wsSetupError is set', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false, wsSetupError: 'Auth token expired' }
    renderSettings()
    expect(screen.getByText('Auth token expired')).toBeInTheDocument()
  })
})
