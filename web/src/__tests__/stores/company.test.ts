import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useCompanyStore } from '@/stores/company'

vi.mock('@/api/endpoints/company', () => ({
  getCompanyConfig: vi.fn(),
  getDepartmentHealth: vi.fn(),
  updateCompany: vi.fn(),
  createDepartment: vi.fn(),
  updateDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  reorderDepartments: vi.fn(),
  createAgentOrg: vi.fn(),
  updateAgentOrg: vi.fn(),
  deleteAgent: vi.fn(),
  reorderAgents: vi.fn(),
}))

import {
  getCompanyConfig,
  getDepartmentHealth,
  updateCompany,
  createDepartment,
  updateDepartment,
  deleteDepartment,
  reorderDepartments,
  createAgentOrg,
  updateAgentOrg,
  deleteAgent,
  reorderAgents,
} from '@/api/endpoints/company'
import type { CompanyConfig, DepartmentHealth } from '@/api/types'
import { makeAgent, makeCompanyConfig, makeDepartment } from '../helpers/factories'

const mockGetCompanyConfig = vi.mocked(getCompanyConfig)
const mockGetDepartmentHealth = vi.mocked(getDepartmentHealth)
const mockUpdateCompany = vi.mocked(updateCompany)
const mockCreateDepartment = vi.mocked(createDepartment)
const mockUpdateDepartment = vi.mocked(updateDepartment)
const mockDeleteDepartment = vi.mocked(deleteDepartment)
const mockReorderDepartments = vi.mocked(reorderDepartments)
const mockCreateAgent = vi.mocked(createAgentOrg)
const mockUpdateAgent = vi.mocked(updateAgentOrg)
const mockDeleteAgent = vi.mocked(deleteAgent)
const mockReorderAgents = vi.mocked(reorderAgents)

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

function resetStore() {
  useCompanyStore.setState({
    config: null,
    departmentHealths: [],
    loading: false,
    error: null,
    healthError: null,
    saving: false,
    saveError: null,
  })
}

describe('useCompanyStore', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('starts with null config and empty health', () => {
    const state = useCompanyStore.getState()
    expect(state.config).toBeNull()
    expect(state.departmentHealths).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.healthError).toBeNull()
    expect(state.saving).toBe(false)
    expect(state.saveError).toBeNull()
  })

  it('fetchCompanyData sets config on success', async () => {
    mockGetCompanyConfig.mockResolvedValue(mockConfig)
    await useCompanyStore.getState().fetchCompanyData()
    const state = useCompanyStore.getState()
    expect(state.config).toEqual(mockConfig)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchCompanyData sets error on failure and rethrows', async () => {
    mockGetCompanyConfig.mockRejectedValue(new Error('Network error'))
    await expect(useCompanyStore.getState().fetchCompanyData()).rejects.toThrow('Network error')
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

  it('fetchDepartmentHealths sets healthError when all fetches fail', async () => {
    useCompanyStore.setState({ config: mockConfig })
    mockGetDepartmentHealth.mockRejectedValue(new Error('Service down'))

    await useCompanyStore.getState().fetchDepartmentHealths()
    const state = useCompanyStore.getState()
    expect(state.departmentHealths).toEqual([])
    expect(state.healthError).toBe('Failed to fetch department health data')
  })

  it('fetchDepartmentHealths clears healthError on success', async () => {
    useCompanyStore.setState({ config: mockConfig, healthError: 'previous error' })
    mockGetDepartmentHealth.mockResolvedValue(mockDeptHealth)

    await useCompanyStore.getState().fetchDepartmentHealths()
    expect(useCompanyStore.getState().healthError).toBeNull()
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

  // ── Mutations ──────────────────────────────────────────────

  describe('updateCompany', () => {
    it('updates config on success', async () => {
      const updated = { ...mockConfig, company_name: 'New Name' }
      mockUpdateCompany.mockResolvedValue(updated)
      useCompanyStore.setState({ config: mockConfig })

      await useCompanyStore.getState().updateCompany({ company_name: 'New Name' })
      expect(useCompanyStore.getState().config?.company_name).toBe('New Name')
      expect(useCompanyStore.getState().saving).toBe(false)
    })

    it('sets saveError on failure', async () => {
      mockUpdateCompany.mockRejectedValue(new Error('Forbidden'))
      useCompanyStore.setState({ config: mockConfig })

      await expect(useCompanyStore.getState().updateCompany({ company_name: 'X' })).rejects.toThrow('Forbidden')
      expect(useCompanyStore.getState().saveError).toBe('Forbidden')
      expect(useCompanyStore.getState().saving).toBe(false)
    })
  })

  describe('createDepartment', () => {
    it('appends new department to config', async () => {
      const newDept = makeDepartment('design')
      mockCreateDepartment.mockResolvedValue(newDept)
      useCompanyStore.setState({ config: mockConfig })

      const result = await useCompanyStore.getState().createDepartment({
        name: 'design',
        display_name: 'Design',
      })
      expect(result).toEqual(newDept)
      expect(useCompanyStore.getState().config!.departments).toHaveLength(2)
    })

    it('throws on failure without modifying config', async () => {
      mockCreateDepartment.mockRejectedValue(new Error('Conflict'))
      useCompanyStore.setState({ config: mockConfig })

      await expect(
        useCompanyStore.getState().createDepartment({ name: 'x', display_name: 'X' }),
      ).rejects.toThrow('Conflict')
      expect(useCompanyStore.getState().config!.departments).toHaveLength(1)
    })
  })

  describe('updateDepartment', () => {
    it('replaces department in config', async () => {
      const updated = makeDepartment('engineering', { display_name: 'Eng Team' })
      mockUpdateDepartment.mockResolvedValue(updated)
      useCompanyStore.setState({ config: mockConfig })

      const result = await useCompanyStore.getState().updateDepartment('engineering', {
        display_name: 'Eng Team',
      })
      expect(result.display_name).toBe('Eng Team')
      expect(useCompanyStore.getState().config!.departments[0]!.display_name).toBe('Eng Team')
    })
  })

  describe('deleteDepartment', () => {
    it('removes department from config', async () => {
      mockDeleteDepartment.mockResolvedValue(undefined)
      useCompanyStore.setState({ config: mockConfig })

      await useCompanyStore.getState().deleteDepartment('engineering')
      expect(useCompanyStore.getState().config!.departments).toHaveLength(0)
    })
  })

  describe('reorderDepartments', () => {
    it('updates config with reordered result', async () => {
      const reordered = {
        ...mockConfig,
        departments: [makeDepartment('product'), makeDepartment('engineering')],
      }
      mockReorderDepartments.mockResolvedValue(reordered)
      useCompanyStore.setState({ config: mockConfig })

      await useCompanyStore.getState().reorderDepartments(['product', 'engineering'])
      expect(useCompanyStore.getState().config!.departments[0]!.name).toBe('product')
    })

    it('sets saveError on failure', async () => {
      mockReorderDepartments.mockRejectedValue(new Error('Reorder denied'))
      useCompanyStore.setState({ config: mockConfig })

      await expect(
        useCompanyStore.getState().reorderDepartments(['product', 'engineering']),
      ).rejects.toThrow('Reorder denied')
      expect(useCompanyStore.getState().saveError).toBe('Reorder denied')
      expect(useCompanyStore.getState().saving).toBe(false)
    })
  })

  describe('createAgent', () => {
    it('appends new agent to config', async () => {
      const newAgent = makeAgent('dave')
      mockCreateAgent.mockResolvedValue(newAgent)
      useCompanyStore.setState({ config: mockConfig })

      const result = await useCompanyStore.getState().createAgent({
        name: 'dave',
        role: 'Designer',
        department: 'engineering',
        level: 'mid',
      })
      expect(result).toEqual(newAgent)
      expect(useCompanyStore.getState().config!.agents).toHaveLength(1)
    })
  })

  describe('updateAgent', () => {
    it('replaces agent in config', async () => {
      const agent = makeAgent('alice')
      const updated = { ...agent, role: 'Senior Dev' }
      mockUpdateAgent.mockResolvedValue(updated)
      useCompanyStore.setState({ config: { ...mockConfig, agents: [agent] } })

      const result = await useCompanyStore.getState().updateAgent('alice', { role: 'Senior Dev' })
      expect(result.role).toBe('Senior Dev')
    })
  })

  describe('deleteAgent', () => {
    it('removes agent from config', async () => {
      const agent = makeAgent('alice')
      mockDeleteAgent.mockResolvedValue(undefined)
      useCompanyStore.setState({ config: { ...mockConfig, agents: [agent] } })

      await useCompanyStore.getState().deleteAgent('alice')
      expect(useCompanyStore.getState().config!.agents).toHaveLength(0)
    })
  })

  describe('reorderAgents', () => {
    it('calls API and clears saving flag', async () => {
      mockReorderAgents.mockResolvedValue(mockConfig.departments[0]!)
      useCompanyStore.setState({ config: mockConfig })

      await useCompanyStore.getState().reorderAgents('engineering', ['a-2', 'a-1'])
      expect(mockReorderAgents).toHaveBeenCalledWith('engineering', { agent_ids: ['a-2', 'a-1'] })
      expect(useCompanyStore.getState().saving).toBe(false)
    })

    it('sets saveError on failure', async () => {
      mockReorderAgents.mockRejectedValue(new Error('Reorder failed'))
      useCompanyStore.setState({ config: mockConfig })

      await expect(
        useCompanyStore.getState().reorderAgents('engineering', ['a-2', 'a-1']),
      ).rejects.toThrow('Reorder failed')
      expect(useCompanyStore.getState().saveError).toBe('Reorder failed')
      expect(useCompanyStore.getState().saving).toBe(false)
    })
  })

  // ── Optimistic helpers ─────────────────────────────────────

  describe('optimisticReorderDepartments', () => {
    it('reorders departments and returns rollback', () => {
      const config = makeCompanyConfig()
      useCompanyStore.setState({ config })

      const rollback = useCompanyStore.getState().optimisticReorderDepartments(['product', 'engineering'])
      expect(useCompanyStore.getState().config!.departments[0]!.name).toBe('product')

      rollback()
      expect(useCompanyStore.getState().config!.departments[0]!.name).toBe('engineering')
    })

    it('returns no-op when config is null', () => {
      const rollback = useCompanyStore.getState().optimisticReorderDepartments(['a'])
      expect(rollback).toBeTypeOf('function')
      rollback() // should not throw
    })
  })

  describe('optimisticReorderAgents', () => {
    it('reorders agents within department and returns rollback', () => {
      const config = makeCompanyConfig()
      useCompanyStore.setState({ config })

      const agentIds = config.agents
        .filter((a) => a.department === 'engineering')
        .map((a) => a.id)
        .reverse()

      const rollback = useCompanyStore.getState().optimisticReorderAgents('engineering', agentIds)

      const reordered = useCompanyStore.getState().config!.agents.filter(
        (a) => a.department === 'engineering',
      )
      expect(reordered.map((a) => a.id)).toEqual(agentIds)

      rollback()
      const restored = useCompanyStore.getState().config!.agents.filter(
        (a) => a.department === 'engineering',
      )
      expect(restored.map((a) => a.id)).toEqual(agentIds.toReversed())
    })
  })
})
