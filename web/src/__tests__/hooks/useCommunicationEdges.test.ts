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
    // Simulate two full pages. Offset advances by data.length, not limit.
    const page1Data = Array.from({ length: 100 }, (_, i) => ({
      sender: `agent-${i}`,
      to: `agent-${i + 1}`,
    }))
    const page2Data = [{ sender: 'carol', to: 'dave' }]
    mockListMessages
      .mockResolvedValueOnce({
        data: page1Data,
        total: 101,
        offset: 0,
        limit: 100,
      })
      .mockResolvedValueOnce({
        data: page2Data,
        total: 101,
        offset: 100,
        limit: 100,
      })

    const { result } = renderHook(() => useCommunicationEdges(true))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.links.length).toBeGreaterThan(0)
    expect(mockListMessages).toHaveBeenCalledTimes(2)
    expect(mockListMessages).toHaveBeenNthCalledWith(1, expect.objectContaining({ offset: 0, limit: 100 }))
    expect(mockListMessages).toHaveBeenNthCalledWith(2, expect.objectContaining({ offset: 100, limit: 100 }))
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
