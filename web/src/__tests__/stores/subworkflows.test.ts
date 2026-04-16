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
    expect(useToastStore.getState().toasts[0]!.variant).toBe('success')
  })

  it('returns false and emits an error toast on API failure', async () => {
    const api = await importApi()
    vi.mocked(api.deleteSubworkflow).mockRejectedValue(new Error('boom'))

    const result = await useSubworkflowsStore.getState().deleteSubworkflow('swf-1', '2.0')

    expect(result).toBe(false)
    expect(api.listSubworkflows).not.toHaveBeenCalled()
    expect(useToastStore.getState().toasts[0]!.variant).toBe('error')
  })
})
