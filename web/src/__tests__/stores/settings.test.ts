import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSettingsStore } from '@/stores/settings'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('@/api/endpoints/settings', () => ({
  getSchema: vi.fn(),
  getAllSettings: vi.fn(),
  updateSetting: vi.fn(),
  resetSetting: vi.fn(),
}))

const mockDefinition: SettingDefinition = {
  namespace: 'budget',
  key: 'total_monthly',
  type: 'float',
  default: '100.0',
  description: 'Monthly budget in USD',
  group: 'Limits',
  level: 'basic',
  sensitive: false,
  restart_required: false,
  enum_values: [],
  validator_pattern: null,
  min_value: 0.0,
  max_value: null,
  yaml_path: 'budget.total_monthly',
}

const mockAdvancedDefinition: SettingDefinition = {
  ...mockDefinition,
  key: 'auto_downgrade_enabled',
  type: 'bool',
  default: 'false',
  description: 'Enable automatic model downgrade',
  group: 'Auto-Downgrade',
  level: 'advanced',
}

const mockSecurityDefinition: SettingDefinition = {
  ...mockDefinition,
  namespace: 'security',
  key: 'enabled',
  type: 'bool',
  default: 'true',
  description: 'Enable security engine',
  group: 'General',
}

const mockEntry: SettingEntry = {
  definition: mockDefinition,
  value: '100.0',
  source: 'default',
  updated_at: null,
}

const mockAdvancedEntry: SettingEntry = {
  definition: mockAdvancedDefinition,
  value: 'false',
  source: 'default',
  updated_at: null,
}

const mockSecurityEntry: SettingEntry = {
  definition: mockSecurityDefinition,
  value: 'true',
  source: 'yaml',
  updated_at: null,
}

describe('useSettingsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('initializes with empty state', () => {
    const store = useSettingsStore()
    expect(store.schema).toEqual([])
    expect(store.entries).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.savingKey).toBeNull()
    expect(store.showAdvanced).toBe(false)
  })

  it('fetchAll loads schema and entries in parallel', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition, mockSecurityDefinition])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([mockEntry, mockSecurityEntry])

    const store = useSettingsStore()
    await store.fetchAll()

    expect(settingsApi.getSchema).toHaveBeenCalledOnce()
    expect(settingsApi.getAllSettings).toHaveBeenCalledOnce()
    expect(store.schema).toHaveLength(2)
    expect(store.entries).toHaveLength(2)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchAll sets loading during fetch', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    let resolveSchema!: (v: SettingDefinition[]) => void
    vi.mocked(settingsApi.getSchema).mockReturnValue(
      new Promise((r) => { resolveSchema = r }),
    )
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([])

    const store = useSettingsStore()
    const promise = store.fetchAll()

    expect(store.loading).toBe(true)
    resolveSchema([])
    await promise
    expect(store.loading).toBe(false)
  })

  it('fetchAll sets error on failure', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockRejectedValue(new Error('Network error'))
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([])

    const store = useSettingsStore()
    await store.fetchAll()

    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })

  it('fetchAll ignores stale responses via generation counter', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    let resolveFirst!: (v: SettingDefinition[]) => void
    vi.mocked(settingsApi.getSchema)
      .mockReturnValueOnce(new Promise((r) => { resolveFirst = r }))
      .mockResolvedValueOnce([mockDefinition])
    vi.mocked(settingsApi.getAllSettings)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([mockEntry])

    const store = useSettingsStore()

    // First fetch (will be slow)
    const first = store.fetchAll()

    // Second fetch (will be fast)
    await store.fetchAll()
    expect(store.schema).toEqual([mockDefinition])

    // Now resolve the first (stale) -- should be ignored
    resolveFirst([mockSecurityDefinition])
    await first
    expect(store.schema).toEqual([mockDefinition])
  })

  it('namespaces returns unique sorted namespaces from schema', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockResolvedValue([
      mockSecurityDefinition,
      mockDefinition,
      mockAdvancedDefinition,
    ])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([])

    const store = useSettingsStore()
    await store.fetchAll()

    // budget comes before security in NAMESPACE_ORDER
    expect(store.namespaces).toEqual(['budget', 'security'])
  })

  it('entriesByNamespace filters entries by namespace', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition, mockSecurityDefinition])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([mockEntry, mockSecurityEntry])

    const store = useSettingsStore()
    await store.fetchAll()

    expect(store.entriesByNamespace('budget')).toEqual([mockEntry])
    expect(store.entriesByNamespace('security')).toEqual([mockSecurityEntry])
    expect(store.entriesByNamespace('api')).toEqual([])
  })

  it('updateSetting calls API and refreshes entries', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    const updatedEntry: SettingEntry = { ...mockEntry, value: '200.0', source: 'db' }
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition])
    vi.mocked(settingsApi.getAllSettings)
      .mockResolvedValueOnce([mockEntry])
      .mockResolvedValueOnce([updatedEntry])
    vi.mocked(settingsApi.updateSetting).mockResolvedValue(updatedEntry)

    const store = useSettingsStore()
    await store.fetchAll()
    expect(store.entries[0].value).toBe('100.0')

    await store.updateSetting('budget', 'total_monthly', '200.0')

    expect(settingsApi.updateSetting).toHaveBeenCalledWith('budget', 'total_monthly', { value: '200.0' })
    // After update, the store re-fetches entries
    expect(store.entries[0].value).toBe('200.0')
    expect(store.savingKey).toBeNull()
  })

  it('updateSetting sets savingKey during save', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    let resolveUpdate!: (v: SettingEntry) => void
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([mockEntry])
    vi.mocked(settingsApi.updateSetting).mockReturnValue(
      new Promise((r) => { resolveUpdate = r }),
    )

    const store = useSettingsStore()
    await store.fetchAll()
    const promise = store.updateSetting('budget', 'total_monthly', '200.0')

    expect(store.savingKey).toBe('budget/total_monthly')
    resolveUpdate(mockEntry)
    await promise
    expect(store.savingKey).toBeNull()
  })

  it('updateSetting propagates errors and clears savingKey', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([mockEntry])
    vi.mocked(settingsApi.updateSetting).mockRejectedValue(new Error('Validation failed'))

    const store = useSettingsStore()
    await store.fetchAll()

    await expect(store.updateSetting('budget', 'total_monthly', 'bad'))
      .rejects.toThrow('Validation failed')
    expect(store.savingKey).toBeNull()
  })

  it('resetSetting calls API and refreshes entries', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    const dbEntry: SettingEntry = { ...mockEntry, value: '200.0', source: 'db' }
    vi.mocked(settingsApi.getSchema).mockResolvedValue([mockDefinition])
    vi.mocked(settingsApi.getAllSettings)
      .mockResolvedValueOnce([dbEntry])
      .mockResolvedValueOnce([mockEntry])
    vi.mocked(settingsApi.resetSetting).mockResolvedValue(undefined)

    const store = useSettingsStore()
    await store.fetchAll()
    expect(store.entries[0].source).toBe('db')

    await store.resetSetting('budget', 'total_monthly')

    expect(settingsApi.resetSetting).toHaveBeenCalledWith('budget', 'total_monthly')
    expect(store.entries[0].source).toBe('default')
  })

  it('toggleAdvanced flips state and persists to localStorage', () => {
    const store = useSettingsStore()
    expect(store.showAdvanced).toBe(false)

    store.toggleAdvanced()
    expect(store.showAdvanced).toBe(true)
    expect(localStorage.getItem('settings_show_advanced')).toBe('true')

    store.toggleAdvanced()
    expect(store.showAdvanced).toBe(false)
    expect(localStorage.getItem('settings_show_advanced')).toBe('false')
  })

  it('reads showAdvanced from localStorage on init', () => {
    localStorage.setItem('settings_show_advanced', 'true')
    const store = useSettingsStore()
    expect(store.showAdvanced).toBe(true)
  })

  it('handles invalid localStorage value gracefully', () => {
    localStorage.setItem('settings_show_advanced', 'garbage')
    const store = useSettingsStore()
    expect(store.showAdvanced).toBe(false)
  })
})
