import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSubworkflowsStore } from '@/stores/subworkflows'
import { useToastStore } from '@/stores/toast'

vi.mock('@/api/endpoints/subworkflows', () => ({
  listSubworkflows: vi.fn(),
  searchSubworkflows: vi.fn(),
  deleteSubworkflow: vi.fn(),
}))

async function importApi() {
  return await import('@/api/endpoints/subworkflows')
}

function resetStore() {
  useSubworkflowsStore.setState({
    subworkflows: [],
    listLoading: false,
    listError: null,
    searchQuery: '',
  })
  useToastStore.setState({ toasts: [] })
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('deleteSubworkflow', () => {
  it('refetches and emits a success toast on success', async () => {
    const api = await importApi()
    vi.mocked(api.deleteSubworkflow).mockResolvedValue(undefined)
    vi.mocked(api.listSubworkflows).mockResolvedValue([])

    const result = await useSubworkflowsStore.getState().deleteSubworkflow('swf-1', '2.0')

    expect(result).toBe(true)
    expect(api.listSubworkflows).toHaveBeenCalledTimes(1)
    const toasts = useToastStore.getState().toasts
    expect(toasts[0]!.variant).toBe('success')
    expect(toasts[0]!.title).toBe('Subworkflow deleted')
  })

  it('returns false and emits an error toast on API failure', async () => {
    const api = await importApi()
    vi.mocked(api.deleteSubworkflow).mockRejectedValue(new Error('boom'))

    const result = await useSubworkflowsStore.getState().deleteSubworkflow('swf-1', '2.0')

    expect(result).toBe(false)
    expect(api.listSubworkflows).not.toHaveBeenCalled()
    const toasts = useToastStore.getState().toasts
    expect(toasts[0]!.variant).toBe('error')
    expect(toasts[0]!.title).toBe('Failed to delete subworkflow')
    expect(toasts[0]!.description).toBe('boom')
  })
})

describe('fetchSubworkflows', () => {
  it('populates subworkflows and clears error on success', async () => {
    const api = await importApi()
    vi.mocked(api.listSubworkflows).mockResolvedValue([])

    useSubworkflowsStore.setState({ listError: 'stale' })
    await useSubworkflowsStore.getState().fetchSubworkflows()

    const state = useSubworkflowsStore.getState()
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBeNull()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('uses searchSubworkflows when a search query is set', async () => {
    const api = await importApi()
    vi.mocked(api.searchSubworkflows).mockResolvedValue([])

    useSubworkflowsStore.setState({ searchQuery: 'needle' })
    await useSubworkflowsStore.getState().fetchSubworkflows()

    expect(api.searchSubworkflows).toHaveBeenCalledWith('needle')
    expect(api.listSubworkflows).not.toHaveBeenCalled()
  })

  it('sets listError on failure without toasting (list-read pattern)', async () => {
    const api = await importApi()
    vi.mocked(api.listSubworkflows).mockRejectedValue(new Error('network down'))

    await useSubworkflowsStore.getState().fetchSubworkflows()

    const state = useSubworkflowsStore.getState()
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBe('network down')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
