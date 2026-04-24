import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { useSubworkflowsStore } from '@/stores/subworkflows'
import { useToastStore } from '@/stores/toast'
import {
  apiError,
  apiSuccess,
  emptyPage,
  paginatedFor,
  voidSuccess,
} from '@/mocks/handlers'
import type { listSubworkflows } from '@/api/endpoints/subworkflows'
import type { SubworkflowSummary } from '@/api/types/workflows'
import { server } from '@/test-setup'

function resetStore() {
  useSubworkflowsStore.setState({
    subworkflows: [],
    listLoading: false,
    listError: null,
    searchQuery: '',
  })
  useToastStore.getState().dismissAll()
}

beforeEach(() => {
  resetStore()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('deleteSubworkflow', () => {
  it('refetches and emits a success toast on success', async () => {
    let refetched = 0
    server.use(
      http.delete('/api/v1/subworkflows/:id/versions/:version', () =>
        HttpResponse.json(voidSuccess()),
      ),
      http.get('/api/v1/subworkflows', () => {
        refetched += 1
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        )
      }),
    )

    const result = await useSubworkflowsStore
      .getState()
      .deleteSubworkflow('swf-1', '2.0')

    expect(result).toBe(true)
    expect(refetched).toBe(1)
    const toasts = useToastStore.getState().toasts
    expect(toasts[0]!.variant).toBe('success')
    expect(toasts[0]!.title).toBe('Subworkflow deleted')
  })

  it('returns false and emits an error toast on API failure', async () => {
    let refetched = 0
    server.use(
      http.delete('/api/v1/subworkflows/:id/versions/:version', () =>
        HttpResponse.json(apiError('boom')),
      ),
      http.get('/api/v1/subworkflows', () => {
        refetched += 1
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        )
      }),
    )

    const result = await useSubworkflowsStore
      .getState()
      .deleteSubworkflow('swf-1', '2.0')

    expect(result).toBe(false)
    expect(refetched).toBe(0)
    const toasts = useToastStore.getState().toasts
    expect(toasts[0]!.variant).toBe('error')
    expect(toasts[0]!.title).toBe('Failed to delete subworkflow')
    expect(toasts[0]!.description).toBe('boom')
  })
})

describe('fetchSubworkflows', () => {
  it('populates subworkflows and clears error on success', async () => {
    server.use(
      http.get('/api/v1/subworkflows', () =>
        HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        ),
      ),
    )

    useSubworkflowsStore.setState({ listError: 'stale' })
    await useSubworkflowsStore.getState().fetchSubworkflows()

    const state = useSubworkflowsStore.getState()
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBeNull()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('uses searchSubworkflows when a search query is set', async () => {
    let searchCalls = 0
    let listCalls = 0
    let searchQuery: string | null = null
    server.use(
      http.get('/api/v1/subworkflows/search', ({ request }) => {
        searchCalls += 1
        searchQuery = new URL(request.url).searchParams.get('q')
        return HttpResponse.json(apiSuccess([]))
      }),
      http.get('/api/v1/subworkflows', () => {
        listCalls += 1
        return HttpResponse.json(apiSuccess([]))
      }),
    )

    useSubworkflowsStore.setState({ searchQuery: 'needle' })
    await useSubworkflowsStore.getState().fetchSubworkflows()

    expect(searchCalls).toBe(1)
    expect(searchQuery).toBe('needle')
    expect(listCalls).toBe(0)
  })

  it('sets listError on failure without toasting (list-read pattern)', async () => {
    server.use(
      http.get('/api/v1/subworkflows', () =>
        HttpResponse.json(apiError('network down')),
      ),
    )

    await useSubworkflowsStore.getState().fetchSubworkflows()

    const state = useSubworkflowsStore.getState()
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBe('network down')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
