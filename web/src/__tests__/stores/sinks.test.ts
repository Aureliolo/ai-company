import type { SinkInfo, TestSinkResult } from '@/api/types'
import { useSinksStore } from '@/stores/sinks'

vi.mock('@/api/endpoints/settings', () => ({
  listSinks: vi.fn(),
  testSinkConfig: vi.fn(),
}))

const { listSinks, testSinkConfig } = await import('@/api/endpoints/settings')

function makeSink(overrides: Partial<SinkInfo> = {}): SinkInfo {
  return {
    identifier: '__console__',
    sink_type: 'console',
    level: 'INFO',
    json_format: false,
    rotation: null,
    is_default: true,
    enabled: true,
    routing_prefixes: [],
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  useSinksStore.setState({
    sinks: [],
    loading: false,
    error: null,
  })
})

describe('fetchSinks', () => {
  it('sets sinks on success', async () => {
    const sinks = [makeSink(), makeSink({ identifier: 'synthorg.log', sink_type: 'file' })]
    vi.mocked(listSinks).mockResolvedValue(sinks)

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    expect(state.sinks).toHaveLength(2)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('sets loading to true during fetch', async () => {
    let resolvePromise!: (value: SinkInfo[]) => void
    vi.mocked(listSinks).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      }),
    )

    const fetchPromise = useSinksStore.getState().fetchSinks()
    expect(useSinksStore.getState().loading).toBe(true)

    resolvePromise([makeSink()])
    await fetchPromise

    expect(useSinksStore.getState().loading).toBe(false)
  })

  it('sets error on failure with Error instance', async () => {
    vi.mocked(listSinks).mockRejectedValue(new Error('Network error'))

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    expect(state.sinks).toHaveLength(0)
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('sets generic error on failure with non-Error', async () => {
    vi.mocked(listSinks).mockRejectedValue('string error')

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    expect(state.error).toBe('Failed to load sinks')
    expect(state.loading).toBe(false)
  })

  it('clears previous error on new fetch', async () => {
    useSinksStore.setState({ error: 'old error' })
    vi.mocked(listSinks).mockResolvedValue([makeSink()])

    await useSinksStore.getState().fetchSinks()

    expect(useSinksStore.getState().error).toBeNull()
  })
})

describe('testConfig', () => {
  it('passes data through to testSinkConfig', async () => {
    const result: TestSinkResult = { valid: true, error: null }
    vi.mocked(testSinkConfig).mockResolvedValue(result)

    const data = { sink_overrides: '{}', custom_sinks: '[]' }
    const response = await useSinksStore.getState().testConfig(data)

    expect(testSinkConfig).toHaveBeenCalledWith(data)
    expect(response).toEqual(result)
  })

  it('propagates errors from testSinkConfig', async () => {
    vi.mocked(testSinkConfig).mockRejectedValue(new Error('Invalid config'))

    const data = { sink_overrides: '{}', custom_sinks: '[]' }
    await expect(useSinksStore.getState().testConfig(data)).rejects.toThrow('Invalid config')
  })
})
