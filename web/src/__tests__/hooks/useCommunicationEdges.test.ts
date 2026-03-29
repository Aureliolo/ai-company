import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

// Mock listMessages
const mockListMessages = vi.fn()

vi.mock('@/api/endpoints/messages', () => ({
  listMessages: (...args: unknown[]) => mockListMessages(...args),
}))

// Import after mock
import { useCommunicationEdges } from '@/hooks/useCommunicationEdges'

describe('useCommunicationEdges', () => {
  beforeEach(() => {
    mockListMessages.mockReset()
  })

  it('returns empty links when disabled', () => {
    const { result } = renderHook(() => useCommunicationEdges(false))
    expect(result.current.links).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(mockListMessages).not.toHaveBeenCalled()
  })

  it('fetches and aggregates messages', async () => {
    mockListMessages.mockResolvedValue({
      data: [
        { sender: 'alice', to: 'bob' },
        { sender: 'bob', to: 'alice' },
        { sender: 'alice', to: 'carol' },
      ],
      total: 3,
      offset: 0,
      limit: 100,
    })

    const { result } = renderHook(() => useCommunicationEdges(true))

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links).toHaveLength(2)
    const abLink = result.current.links.find((l) => l.source === 'alice' && l.target === 'bob')
    expect(abLink).toBeDefined()
    expect(abLink!.volume).toBe(2)
  })

  it('handles pagination across multiple pages', async () => {
    // Simulate a case where the API returns total > offset + limit,
    // requiring a second fetch. The hook sends limit=100, but the server
    // may report a smaller limit in the response (e.g. capped at 1).
    mockListMessages
      .mockResolvedValueOnce({
        data: [{ sender: 'alice', to: 'bob' }],
        total: 200,
        offset: 0,
        limit: 100,
      })
      .mockResolvedValueOnce({
        data: [{ sender: 'carol', to: 'dave' }],
        total: 200,
        offset: 100,
        limit: 100,
      })

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links).toHaveLength(2)
    expect(mockListMessages).toHaveBeenCalledTimes(2)
  })

  it('sets error on API failure', async () => {
    mockListMessages.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.links).toEqual([])
  })

  it('returns empty links when no messages exist', async () => {
    mockListMessages.mockResolvedValue({
      data: [],
      total: 0,
      offset: 0,
      limit: 100,
    })

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links).toEqual([])
    expect(result.current.error).toBeNull()
  })
})
