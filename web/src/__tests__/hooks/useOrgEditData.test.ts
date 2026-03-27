import { renderHook, waitFor } from '@testing-library/react'
import { useCompanyStore } from '@/stores/company'
import { useOrgEditData } from '@/hooks/useOrgEditData'
import { makeCompanyConfig, makeDepartmentHealth } from '../helpers/factories'

const mockFetchCompanyData = vi.fn().mockResolvedValue(undefined)
const mockFetchDepartmentHealths = vi.fn().mockResolvedValue(undefined)
const mockUpdateFromWsEvent = vi.fn()
const mockUpdateCompany = vi.fn().mockResolvedValue(undefined)
const mockCreateDepartment = vi.fn()
const mockUpdateDepartment = vi.fn()
const mockDeleteDepartment = vi.fn().mockResolvedValue(undefined)
const mockReorderDepartments = vi.fn().mockResolvedValue(undefined)
const mockCreateAgent = vi.fn()
const mockUpdateAgent = vi.fn()
const mockDeleteAgent = vi.fn().mockResolvedValue(undefined)
const mockReorderAgents = vi.fn().mockResolvedValue(undefined)
const mockOptReorderDepts = vi.fn().mockReturnValue(() => {})
const mockOptReorderAgents = vi.fn().mockReturnValue(() => {})

const { mockPollingStart, mockPollingStop } = vi.hoisted(() => ({
  mockPollingStart: vi.fn(),
  mockPollingStop: vi.fn(),
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    connected: true,
    reconnectExhausted: false,
    setupError: null,
  }),
}))

vi.mock('@/hooks/usePolling', () => ({
  usePolling: vi.fn().mockReturnValue({
    active: false,
    error: null,
    start: mockPollingStart,
    stop: mockPollingStop,
  }),
}))

function resetStore() {
  useCompanyStore.setState({
    config: null,
    departmentHealths: [],
    loading: false,
    error: null,
    saving: false,
    saveError: null,
    fetchCompanyData: mockFetchCompanyData,
    fetchDepartmentHealths: mockFetchDepartmentHealths,
    updateFromWsEvent: mockUpdateFromWsEvent,
    updateCompany: mockUpdateCompany,
    createDepartment: mockCreateDepartment,
    updateDepartment: mockUpdateDepartment,
    deleteDepartment: mockDeleteDepartment,
    reorderDepartments: mockReorderDepartments,
    createAgent: mockCreateAgent,
    updateAgent: mockUpdateAgent,
    deleteAgent: mockDeleteAgent,
    reorderAgents: mockReorderAgents,
    optimisticReorderDepartments: mockOptReorderDepts,
    optimisticReorderAgents: mockOptReorderAgents,
  })
}

describe('useOrgEditData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchCompanyData on mount', async () => {
    renderHook(() => useOrgEditData())
    await waitFor(() => {
      expect(mockFetchCompanyData).toHaveBeenCalledTimes(1)
    })
  })

  it('returns loading state from store', () => {
    useCompanyStore.setState({ loading: true })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.loading).toBe(true)
  })

  it('returns config from store', () => {
    const config = makeCompanyConfig()
    useCompanyStore.setState({ config })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.config).toEqual(config)
  })

  it('returns departmentHealths from store', () => {
    const healths = [makeDepartmentHealth('engineering')]
    useCompanyStore.setState({ departmentHealths: healths })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.departmentHealths).toEqual(healths)
  })

  it('returns error from store', () => {
    useCompanyStore.setState({ error: 'Something failed' })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.error).toBe('Something failed')
  })

  it('returns saving and saveError from store', () => {
    useCompanyStore.setState({ saving: true, saveError: 'Save failed' })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.saving).toBe(true)
    expect(result.current.saveError).toBe('Save failed')
  })

  it('returns wsConnected as true', () => {
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.wsConnected).toBe(true)
  })

  it('returns wsSetupError from WebSocket hook', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    vi.mocked(useWebSocket).mockReturnValue({
      connected: false,
      reconnectExhausted: false,
      setupError: 'Auth token expired',
    })
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.wsSetupError).toBe('Auth token expired')
    // Restore default mock
    vi.mocked(useWebSocket).mockReturnValue({
      connected: true,
      reconnectExhausted: false,
      setupError: null,
    })
  })

  it('exposes all mutation functions', () => {
    const { result } = renderHook(() => useOrgEditData())
    expect(result.current.updateCompany).toBeTypeOf('function')
    expect(result.current.createDepartment).toBeTypeOf('function')
    expect(result.current.updateDepartment).toBeTypeOf('function')
    expect(result.current.deleteDepartment).toBeTypeOf('function')
    expect(result.current.reorderDepartments).toBeTypeOf('function')
    expect(result.current.createAgent).toBeTypeOf('function')
    expect(result.current.updateAgent).toBeTypeOf('function')
    expect(result.current.deleteAgent).toBeTypeOf('function')
    expect(result.current.reorderAgents).toBeTypeOf('function')
    expect(result.current.optimisticReorderDepartments).toBeTypeOf('function')
    expect(result.current.optimisticReorderAgents).toBeTypeOf('function')
  })
})
