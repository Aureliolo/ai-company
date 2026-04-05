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

  it('subscribes to the agents channel with a single binding', () => {
    renderHook(() => useGlobalNotifications())

    expect(mockUseWebSocket).toHaveBeenCalledTimes(1)
    const [options] = mockUseWebSocket.mock.calls[0]!
    const bindings = (options as { bindings: Array<{ channel: string }> }).bindings
    expect(bindings).toHaveLength(1)
    expect(bindings[0]!.channel).toBe('agents')
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

  it('renders a warning toast when WebSocket setup fails', () => {
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: false,
      setupError: 'WebSocket connection failed.',
    })

    renderHook(() => useGlobalNotifications())

    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe('warning')
    expect(toasts[0]!.title).toBe('Live notifications unavailable')
  })

  it('renders an error toast when reconnect is exhausted', () => {
    mockUseWebSocket.mockReturnValue({
      connected: false,
      reconnectExhausted: true,
      setupError: null,
    })

    renderHook(() => useGlobalNotifications())

    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe('error')
    expect(toasts[0]!.title).toBe('Live notifications disconnected')
  })

  it('does not emit a toast when everything is healthy', () => {
    renderHook(() => useGlobalNotifications())
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
