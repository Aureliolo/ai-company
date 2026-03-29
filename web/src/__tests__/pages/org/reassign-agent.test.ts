import { describe, expect, it, beforeEach, vi } from 'vitest'

// Mock API endpoints to prevent real HTTP calls
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

import { useCompanyStore } from '@/stores/company'
import { makeAgent, makeCompanyConfig, makeDepartment } from '@/__tests__/helpers/factories'

function testConfig() {
  return makeCompanyConfig({
    agents: [
      makeAgent('alice', { department: 'engineering' }),
      makeAgent('bob', { department: 'design' }),
    ],
    departments: [
      makeDepartment('engineering'),
      makeDepartment('design'),
      makeDepartment('product'),
    ],
  })
}

describe('optimisticReassignAgent', () => {
  beforeEach(() => {
    useCompanyStore.setState({ config: testConfig(), error: null })
  })

  it('moves agent from one department to another', () => {
    useCompanyStore.getState().optimisticReassignAgent('alice', 'design')
    const config = useCompanyStore.getState().config!
    const alice = config.agents.find((a) => a.name === 'alice')
    expect(alice!.department).toBe('design')
  })

  it('rollback restores original department', () => {
    const rollback = useCompanyStore.getState().optimisticReassignAgent('alice', 'design')
    expect(useCompanyStore.getState().config!.agents.find((a) => a.name === 'alice')!.department).toBe('design')

    rollback()
    expect(useCompanyStore.getState().config!.agents.find((a) => a.name === 'alice')!.department).toBe('engineering')
  })

  it('returns no-op when reassigning to same department', () => {
    const rollback = useCompanyStore.getState().optimisticReassignAgent('alice', 'engineering')
    const alice = useCompanyStore.getState().config!.agents.find((a) => a.name === 'alice')
    expect(alice!.department).toBe('engineering')
    rollback()
    expect(useCompanyStore.getState().config!.agents.find((a) => a.name === 'alice')!.department).toBe('engineering')
  })

  it('returns no-op when config is null', () => {
    useCompanyStore.setState({ config: null })
    const rollback = useCompanyStore.getState().optimisticReassignAgent('alice', 'design')
    expect(useCompanyStore.getState().config).toBeNull()
    rollback()
    expect(useCompanyStore.getState().config).toBeNull()
  })

  it('returns no-op when agent not found', () => {
    const rollback = useCompanyStore.getState().optimisticReassignAgent('unknown', 'design')
    rollback()
    expect(useCompanyStore.getState().config!.agents).toHaveLength(2)
  })

  it('preserves other agents during reassignment', () => {
    useCompanyStore.getState().optimisticReassignAgent('alice', 'product')
    const config = useCompanyStore.getState().config!
    const bob = config.agents.find((a) => a.name === 'bob')
    expect(bob!.department).toBe('design')
  })

  it('rollback preserves concurrent changes to other agents', () => {
    const rollback = useCompanyStore.getState().optimisticReassignAgent('alice', 'product')
    useCompanyStore.getState().optimisticReassignAgent('bob', 'engineering')

    rollback()
    const config = useCompanyStore.getState().config!
    expect(config.agents.find((a) => a.name === 'alice')!.department).toBe('engineering')
    expect(config.agents.find((a) => a.name === 'bob')!.department).toBe('engineering')
  })

  it('stale rollback does not overwrite newer reassignment of same agent', () => {
    const rollbackOld = useCompanyStore.getState().optimisticReassignAgent('alice', 'design')
    useCompanyStore.getState().optimisticReassignAgent('alice', 'product')

    // Old rollback fires after newer reassignment -- should be a no-op
    rollbackOld()
    const alice = useCompanyStore.getState().config!.agents.find((a) => a.name === 'alice')
    expect(alice!.department).toBe('product')
  })
})
