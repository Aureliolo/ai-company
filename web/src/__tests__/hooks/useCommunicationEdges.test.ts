import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { useCommunicationEdges } from '@/hooks/useCommunicationEdges'
import { apiError, paginatedFor } from '@/mocks/handlers'
import type { listMessages } from '@/api/endpoints/messages'
import { server } from '@/test-setup'
import type { Message } from '@/api/types/messages'

type MessageSeed = { sender: string; to: string }

function paginated(
  data: MessageSeed[],
  meta: { total: number; offset: number; limit: number },
) {
  return paginatedFor<typeof listMessages>({
    // Seeds are minimal sender/to records; the hook only reads those two
    // fields, but paginatedFor's type parameter demands the full Message
    // shape. Cast through `unknown` to keep the handler focused on the
    // fields under test.
    data: data as unknown as Message[],
    total: meta.total,
    offset: meta.offset,
    limit: meta.limit,
  })
}

describe('useCommunicationEdges', () => {
  let messagesCalls: Array<{
    offset: string | null
    limit: string | null
  }> = []

  beforeEach(() => {
    messagesCalls = []
  })

  it('returns empty links when disabled', () => {
    const { result } = renderHook(() => useCommunicationEdges(false))
    expect(result.current.links).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(messagesCalls).toHaveLength(0)
  })

  it('fetches and aggregates messages', async () => {
    server.use(
      http.get('/api/v1/messages', () =>
        HttpResponse.json(
          paginated(
            [
              { sender: 'alice', to: 'bob' },
              { sender: 'bob', to: 'alice' },
              { sender: 'alice', to: 'carol' },
            ],
            { total: 3, offset: 0, limit: 100 },
          ),
        ),
      ),
    )

    const { result } = renderHook(() => useCommunicationEdges(true))

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links).toHaveLength(2)
    const abLink = result.current.links.find(
      (l) => l.source === 'alice' && l.target === 'bob',
    )
    expect(abLink).toBeDefined()
    expect(abLink!.volume).toBe(2)
  })

  it('handles pagination across multiple pages', async () => {
    const page1Data = Array.from({ length: 100 }, (_, i) => ({
      sender: `agent-${i}`,
      to: `agent-${i + 1}`,
    }))
    const page2Data = [{ sender: 'carol', to: 'dave' }]
    server.use(
      http.get('/api/v1/messages', ({ request }) => {
        const params = new URL(request.url).searchParams
        messagesCalls.push({
          offset: params.get('offset'),
          limit: params.get('limit'),
        })
        if (params.get('offset') === '100') {
          return HttpResponse.json(
            paginated(page2Data, { total: 101, offset: 100, limit: 100 }),
          )
        }
        return HttpResponse.json(
          paginated(page1Data, { total: 101, offset: 0, limit: 100 }),
        )
      }),
    )

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links.length).toBeGreaterThan(0)
    expect(messagesCalls).toHaveLength(2)
    expect(messagesCalls[0]).toEqual({ offset: '0', limit: '100' })
    expect(messagesCalls[1]).toEqual({ offset: '100', limit: '100' })
  })

  it('sets error on API failure', async () => {
    server.use(
      http.get('/api/v1/messages', () =>
        HttpResponse.json(apiError('Network error')),
      ),
    )

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.links).toEqual([])
  })

  it('returns empty links when no messages exist', async () => {
    server.use(
      http.get('/api/v1/messages', () =>
        HttpResponse.json(paginated([], { total: 0, offset: 0, limit: 100 })),
      ),
    )

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links).toEqual([])
    expect(result.current.error).toBeNull()
  })
})
