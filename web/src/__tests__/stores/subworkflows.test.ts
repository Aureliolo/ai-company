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
    loadingMore: false,
    listError: null,
    searchQuery: '',
    nextCursor: null,
    hasMore: false,
  })
  useToastStore.getState().dismissAll()
}

function buildSummary(
  overrides: Partial<SubworkflowSummary> = {},
): SubworkflowSummary {
  return {
    subworkflow_id: 'sub-default',
    latest_version: '1.0.0',
    name: 'Default',
    description: '',
    input_count: 0,
    output_count: 0,
    version_count: 1,
    ...overrides,
  }
}

function pageOf(
  summaries: readonly SubworkflowSummary[],
  cursor: string | null = null,
): {
  data: SubworkflowSummary[]
  total: number | null
  offset: number
  limit: number
  nextCursor: string | null
  hasMore: boolean
  pagination: {
    total: number | null
    offset: number
    limit: number
    next_cursor: string | null
    has_more: boolean
  }
} {
  const limit = 50
  // Always ``null`` under the keyset wire contract -- the backend
  // skips COUNT on every request and the dashboard derives display
  // counts from ``data.length``.  Reporting a non-null total even
  // on the terminal page would let stores start trusting it for
  // ``hasMore``-style decisions and silently regress when the wire
  // total goes unset under real cursor pagination.
  const total = null
  return {
    data: [...summaries],
    total,
    offset: 0,
    limit,
    nextCursor: cursor,
    hasMore: cursor !== null,
    pagination: {
      total,
      offset: 0,
      limit,
      next_cursor: cursor,
      has_more: cursor !== null,
    },
  }
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
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        )
      }),
    )

    useSubworkflowsStore.setState({ searchQuery: 'needle' })
    await useSubworkflowsStore.getState().fetchSubworkflows()

    expect(searchCalls).toBe(1)
    expect(searchQuery).toBe('needle')
    expect(listCalls).toBe(0)
  })

  it('captures cursor + hasMore from the first page', async () => {
    const sub = buildSummary({ subworkflow_id: 'sub-1' })
    server.use(
      http.get('/api/v1/subworkflows', () =>
        HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(pageOf([sub], 'cursor-2')),
        ),
      ),
    )
    await useSubworkflowsStore.getState().fetchSubworkflows()
    const state = useSubworkflowsStore.getState()
    expect(state.subworkflows).toHaveLength(1)
    expect(state.nextCursor).toBe('cursor-2')
    expect(state.hasMore).toBe(true)
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

describe('fetchMoreSubworkflows', () => {
  it('appends the next page to the existing list', async () => {
    const subA = buildSummary({ subworkflow_id: 'sub-a' })
    const subB = buildSummary({ subworkflow_id: 'sub-b' })
    let cursorSeen: string | null = null
    server.use(
      http.get('/api/v1/subworkflows', ({ request }) => {
        cursorSeen = new URL(request.url).searchParams.get('cursor')
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(pageOf([subB])),
        )
      }),
    )
    useSubworkflowsStore.setState({
      subworkflows: [subA],
      nextCursor: 'cursor-2',
      hasMore: true,
    })
    await useSubworkflowsStore.getState().fetchMoreSubworkflows()
    const state = useSubworkflowsStore.getState()
    expect(cursorSeen).toBe('cursor-2')
    expect(state.subworkflows.map((s) => s.subworkflow_id)).toEqual([
      'sub-a',
      'sub-b',
    ])
    expect(state.hasMore).toBe(false)
    expect(state.nextCursor).toBeNull()
  })

  it('is a no-op while a search query is active', async () => {
    let listCalls = 0
    server.use(
      http.get('/api/v1/subworkflows', () => {
        listCalls += 1
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        )
      }),
    )
    useSubworkflowsStore.setState({
      searchQuery: 'needle',
      nextCursor: 'cursor-2',
      hasMore: true,
    })
    await useSubworkflowsStore.getState().fetchMoreSubworkflows()
    expect(listCalls).toBe(0)
  })

  it('is a no-op when there are no more pages', async () => {
    let listCalls = 0
    server.use(
      http.get('/api/v1/subworkflows', () => {
        listCalls += 1
        return HttpResponse.json(
          paginatedFor<typeof listSubworkflows>(emptyPage<SubworkflowSummary>()),
        )
      }),
    )
    useSubworkflowsStore.setState({ nextCursor: null, hasMore: false })
    await useSubworkflowsStore.getState().fetchMoreSubworkflows()
    expect(listCalls).toBe(0)
  })
})
