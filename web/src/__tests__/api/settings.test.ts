import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  unwrap: vi.fn((response) => response.data.data),
  unwrapVoid: vi.fn(),
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

const mockEntry: SettingEntry = {
  definition: mockDefinition,
  value: '100.0',
  source: 'default',
  updated_at: null,
}

describe('settings API endpoints', () => {
  let apiClient: { get: ReturnType<typeof vi.fn>; put: ReturnType<typeof vi.fn>; delete: ReturnType<typeof vi.fn> }
  let unwrap: ReturnType<typeof vi.fn>

  beforeEach(async () => {
    vi.clearAllMocks()
    const client = await import('@/api/client')
    apiClient = client.apiClient as unknown as typeof apiClient
    unwrap = client.unwrap as unknown as ReturnType<typeof vi.fn>
  })

  it('getSchema fetches all definitions', async () => {
    const data = [mockDefinition]
    apiClient.get.mockResolvedValue({ data: { data, success: true } })
    unwrap.mockReturnValue(data)

    const { getSchema } = await import('@/api/endpoints/settings')
    const result = await getSchema()

    expect(apiClient.get).toHaveBeenCalledWith('/settings/_schema')
    expect(result).toEqual(data)
  })

  it('getNamespaceSchema fetches definitions for a namespace', async () => {
    const data = [mockDefinition]
    apiClient.get.mockResolvedValue({ data: { data, success: true } })
    unwrap.mockReturnValue(data)

    const { getNamespaceSchema } = await import('@/api/endpoints/settings')
    const result = await getNamespaceSchema('budget')

    expect(apiClient.get).toHaveBeenCalledWith('/settings/_schema/budget')
    expect(result).toEqual(data)
  })

  it('getAllSettings fetches all resolved entries', async () => {
    const data = [mockEntry]
    apiClient.get.mockResolvedValue({ data: { data, success: true } })
    unwrap.mockReturnValue(data)

    const { getAllSettings } = await import('@/api/endpoints/settings')
    const result = await getAllSettings()

    expect(apiClient.get).toHaveBeenCalledWith('/settings')
    expect(result).toEqual(data)
  })

  it('getNamespaceSettings fetches entries for a namespace', async () => {
    const data = [mockEntry]
    apiClient.get.mockResolvedValue({ data: { data, success: true } })
    unwrap.mockReturnValue(data)

    const { getNamespaceSettings } = await import('@/api/endpoints/settings')
    const result = await getNamespaceSettings('budget')

    expect(apiClient.get).toHaveBeenCalledWith('/settings/budget')
    expect(result).toEqual(data)
  })

  it('updateSetting sends PUT with value', async () => {
    apiClient.put.mockResolvedValue({ data: { data: mockEntry, success: true } })
    unwrap.mockReturnValue(mockEntry)

    const { updateSetting } = await import('@/api/endpoints/settings')
    const result = await updateSetting('budget', 'total_monthly', { value: '200.0' })

    expect(apiClient.put).toHaveBeenCalledWith('/settings/budget/total_monthly', { value: '200.0' })
    expect(result).toEqual(mockEntry)
  })

  it('resetSetting sends DELETE', async () => {
    apiClient.delete.mockResolvedValue({ data: { data: null, success: true } })

    const { resetSetting } = await import('@/api/endpoints/settings')
    await resetSetting('budget', 'total_monthly')

    expect(apiClient.delete).toHaveBeenCalledWith('/settings/budget/total_monthly')
  })

  it('encodes namespace with special characters', async () => {
    const data: SettingDefinition[] = []
    apiClient.get.mockResolvedValue({ data: { data, success: true } })
    unwrap.mockReturnValue(data)

    const { getNamespaceSchema } = await import('@/api/endpoints/settings')
    await getNamespaceSchema('a/b')

    expect(apiClient.get).toHaveBeenCalledWith('/settings/_schema/a%2Fb')
  })

  it('encodes key with special characters in updateSetting', async () => {
    apiClient.put.mockResolvedValue({ data: { data: mockEntry, success: true } })
    unwrap.mockReturnValue(mockEntry)

    const { updateSetting } = await import('@/api/endpoints/settings')
    await updateSetting('budget', 'a/b', { value: 'test' })

    expect(apiClient.put).toHaveBeenCalledWith('/settings/budget/a%2Fb', { value: 'test' })
  })
})
