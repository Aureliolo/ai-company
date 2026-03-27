import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useCompanyStore } from '@/stores/company'

vi.mock('@/api/endpoints/company', () => ({
  getCompanyConfig: vi.fn(),
  getDepartmentHealth: vi.fn(),
}))

import { getCompanyConfig, getDepartmentHealth } from '@/api/endpoints/company'
import type { CompanyConfig, DepartmentHealth } from '@/api/types'

const mockGetCompanyConfig = vi.mocked(getCompanyConfig)
const mockGetDepartmentHealth = vi.mocked(getDepartmentHealth)

const mockConfig: CompanyConfig = {
  company_name: 'Test Corp',
  agents: [],
  departments: [{ name: 'engineering', display_name: 'Engineering', teams: [] }],
}

const mockDeptHealth: DepartmentHealth = {
  name: 'engineering',
  display_name: 'Engineering',
  health_percent: 85,
  agent_count: 3,
  task_count: 5,
  cost_usd: 12.5,
}

describe('useCompanyStore', () => {
  beforeEach(() => {
    useCompanyStore.setState({
      config: null,
      departmentHealths: [],
      loading: false,
      error: null,
    })
    vi.clearAllMocks()
  })

  it('starts with null config and empty health', () => {
    const state = useCompanyStore.getState()
    expect(state.config).toBeNull()
    expect(state.departmentHealths).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchCompanyData sets config on success', async () => {
    mockGetCompanyConfig.mockResolvedValue(mockConfig)
    await useCompanyStore.getState().fetchCompanyData()
    const state = useCompanyStore.getState()
    expect(state.config).toEqual(mockConfig)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchCompanyData sets error on failure', async () => {
    mockGetCompanyConfig.mockRejectedValue(new Error('Network error'))
    await useCompanyStore.getState().fetchCompanyData()
    const state = useCompanyStore.getState()
    expect(state.config).toBeNull()
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('fetchDepartmentHealths populates array on success', async () => {
    useCompanyStore.setState({ config: mockConfig })
    mockGetDepartmentHealth.mockResolvedValue(mockDeptHealth)

    await useCompanyStore.getState().fetchDepartmentHealths()
    expect(useCompanyStore.getState().departmentHealths).toEqual([mockDeptHealth])
  })

  it('fetchDepartmentHealths does nothing without config', async () => {
    await useCompanyStore.getState().fetchDepartmentHealths()
    expect(mockGetDepartmentHealth).not.toHaveBeenCalled()
  })

  it('fetchDepartmentHealths filters out failed health fetches', async () => {
    const configWithTwoDepts: CompanyConfig = {
      ...mockConfig,
      departments: [
        { name: 'engineering', display_name: 'Engineering', teams: [] },
        { name: 'product', display_name: 'Product', teams: [] },
      ],
    }
    useCompanyStore.setState({ config: configWithTwoDepts })
    mockGetDepartmentHealth
      .mockResolvedValueOnce(mockDeptHealth)
      .mockRejectedValueOnce(new Error('Not found'))

    await useCompanyStore.getState().fetchDepartmentHealths()
    const healths = useCompanyStore.getState().departmentHealths
    expect(healths).toHaveLength(1)
    expect(healths[0]!.name).toBe('engineering')
  })

  it('updateFromWsEvent triggers re-fetch of config and health on agent.hired', async () => {
    mockGetCompanyConfig.mockResolvedValue(mockConfig)
    mockGetDepartmentHealth.mockResolvedValue(mockDeptHealth)
    useCompanyStore.getState().updateFromWsEvent({
      event_type: 'agent.hired',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {},
    })
    await vi.waitFor(() => {
      expect(mockGetCompanyConfig).toHaveBeenCalled()
    })
    await vi.waitFor(() => {
      expect(mockGetDepartmentHealth).toHaveBeenCalled()
    })
  })

  it('updateFromWsEvent triggers re-fetch of config and health on agent.fired', async () => {
    mockGetCompanyConfig.mockResolvedValue(mockConfig)
    mockGetDepartmentHealth.mockResolvedValue(mockDeptHealth)
    useCompanyStore.getState().updateFromWsEvent({
      event_type: 'agent.fired',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {},
    })
    await vi.waitFor(() => {
      expect(mockGetCompanyConfig).toHaveBeenCalled()
    })
    await vi.waitFor(() => {
      expect(mockGetDepartmentHealth).toHaveBeenCalled()
    })
  })

  it('updateFromWsEvent ignores unrelated events', () => {
    useCompanyStore.getState().updateFromWsEvent({
      event_type: 'task.created',
      channel: 'tasks',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {},
    })
    expect(mockGetCompanyConfig).not.toHaveBeenCalled()
  })
})
