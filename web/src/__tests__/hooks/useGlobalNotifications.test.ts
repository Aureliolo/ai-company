import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGlobalNotifications } from '@/hooks/useGlobalNotifications'
import { useAgentsStore } from '@/stores/agents'
import { useToastStore } from '@/stores/toast'
import type { WsEvent } from '@/api/types'

// Mock the useWebSocket hook so we can control connection state and capture
// the bindings that useGlobalNotifications subscribes with.
const mockUseWebSocket = vi.fn()
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}))

describe('useGlobalNotifications', () => {
  beforeEach(() => {
    mockUseWebSocket.mockReset()
    mockUseWebSocket.mockReturnValue({
      connected: true,
      reconnectExhausted: false,
      setupError: null,
    })
    useAgentsStore.setState({ runtimeStatuses: {} })
    useToastStore.getState().dismissAll()
  })

  it('subscribes to the agents channel', () => {
    renderHook(() => useGlobalNotifications())

    expect(mockUseWebSocket).toHaveBeenCalledTimes(1)
    const [options] = mockUseWebSocket.mock.calls[0]!
    const bindings = (options as { bindings: Array<{ channel: string }> }).bindings
    // Shape assertion (not count) so adding channels does not break the test.
    expect(bindings.some((b) => b.channel === 'agents')).toBe(true)
  })

  it('dispatches WS events to the agents store', () => {
    renderHook(() => useGlobalNotifications())

    const [options] = mockUseWebSocket.mock.calls[0]!
    const { bindings } = options as {
      bindings: Array<{ channel: string; handler: (event: WsEvent) => void }>
    }

    bindings[0]!.handler({
      event_type: 'agent.status_changed',
      channel: 'agents',
      timestamp: '2026-04-05T10:00:00Z',
      payload: { agent_id: 'agent-1', status: 'active' },
    })

    expect(useAgentsStore.getState().runtimeStatuses['agent-1']).toBe('active')
  })

  it('forwards personality.trimmed events to the toast queue', () => {
    renderHook(() => useGlobalNotifications())

    const [options] = mockUseWebSocket.mock.calls[0]!
    const { bindings } = options as {
      bindings: Array<{ channel: string; handler: (event: WsEvent) => void }>
    }

    bindings[0]!.handler({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-04-05T10:00:00Z',
      payload: {
        agent_id: 'agent-1',
        agent_name: 'Alice',
        task_id: 'task-1',
        before_tokens: 600,
        after_tokens: 120,
        max_tokens: 200,
        trim_tier: 2,
        budget_met: true,
      },
    })

    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.title).toBe('Personality trimmed')
    expect(toasts[0]!.variant).toBe('info')
  })

  it.each([
    {
      name: 'warning toast when WebSocket setup fails',
      wsState: {
        connected: false,
        reconnectExhausted: false,
        setupError: 'WebSocket connection failed.',
      },
      expectedVariant: 'warning' as const,
      expectedTitle: 'Live notifications unavailable',
    },
    {
      name: 'error toast when reconnect is exhausted',
      wsState: {
        connected: false,
        reconnectExhausted: true,
        setupError: null,
      },
      expectedVariant: 'error' as const,
      expectedTitle: 'Live notifications disconnected',
    },
  ])('renders a $name', ({ wsState, expectedVariant, expectedTitle }) => {
    mockUseWebSocket.mockReturnValue(wsState)

    renderHook(() => useGlobalNotifications())

    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe(expectedVariant)
    expect(toasts[0]!.title).toBe(expectedTitle)
  })

  it('does not emit a toast when everything is healthy', () => {
    renderHook(() => useGlobalNotifications())
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('deduplicates identical setupError values across re-renders', () => {
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: false,
      setupError: 'WebSocket connection failed.',
    })

    const { rerender } = renderHook(() => useGlobalNotifications())
    rerender()
    rerender()

    // lastSetupErrorRef dedupes identical errors across re-renders -- only a
    // single toast should have been emitted.
    expect(useToastStore.getState().toasts).toHaveLength(1)
  })

  it('resets dedupe refs when the WS successfully reconnects', () => {
    // 1. WS down with setup error -> one warning toast.
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: false,
      setupError: 'First failure',
    })
    const { rerender } = renderHook(() => useGlobalNotifications())
    expect(useToastStore.getState().toasts).toHaveLength(1)
    useToastStore.getState().dismissAll()

    // 2. Reconnect succeeds -> no toast, but refs should reset so a future
    // failure fires a fresh warning instead of being silently deduped.
    mockUseWebSocket.mockReturnValue({
      connected: true,
      reconnectExhausted: false,
      setupError: null,
    })
    rerender()
    expect(useToastStore.getState().toasts).toHaveLength(0)

    // 3. Second failure with an IDENTICAL string to the first one.  If refs
    // were not reset, dedupe would suppress the toast.
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: false,
      setupError: 'First failure',
    })
    rerender()
    expect(useToastStore.getState().toasts).toHaveLength(1)
  })

  it('stops emitting toasts after unmount', () => {
    mockUseWebSocket.mockReturnValue({
      connected: true,
      reconnectExhausted: false,
      setupError: null,
    })

    const { unmount } = renderHook(() => useGlobalNotifications())
    unmount()

    // After unmount, changing the mock's return value and not re-rendering
    // should not produce any new toasts. This guards against effect re-runs
    // that could occur if the hook leaked a subscription.
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: true,
      setupError: null,
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
