/**
 * Rollback contract for the useWebSocket handler-wiring loop.
 *
 * If any ``onChannelEvent`` call throws partway through the binding
 * loop, the cleanup function must only deregister the handlers that
 * were actually registered -- not blindly iterate every binding and
 * call ``offChannelEvent`` for handlers that were never wired. Without
 * the rollback, the store's internal handler set keeps stale
 * references across reconnects and the cleanup iterates phantom
 * entries.
 */

import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'

function resetStores() {
  sessionStorage.clear()
  localStorage.clear()
  useAuthStore.setState({
    authStatus: 'authenticated',
    user: null,
    loading: false,
  })
  useWebSocketStore.getState().disconnect()
  useWebSocketStore.setState({
    connected: true,
    reconnectExhausted: false,
    subscribedChannels: [],
  })
}

describe('useWebSocket registration rollback', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('only deregisters handlers it successfully registered', async () => {
    const store = useWebSocketStore.getState()

    const handlerA = vi.fn()
    const handlerB = vi.fn()
    const handlerC = vi.fn()
    const handlerD = vi.fn()

    // Fail the third onChannelEvent call so the setup loop aborts
    // partway through -- handlers A and B registered, C threw,
    // D never attempted.
    const onChannelSpy = vi
      .spyOn(store, 'onChannelEvent')
      .mockImplementationOnce(() => {
        // A registers
      })
      .mockImplementationOnce(() => {
        // B registers
      })
      .mockImplementationOnce(() => {
        throw new Error('wiring failure')
      })
      .mockImplementationOnce(() => {
        // D should not be attempted after C throws
      })

    const offChannelSpy = vi.spyOn(store, 'offChannelEvent')

    const { unmount } = renderHook(() =>
      useWebSocket({
        bindings: [
          { channel: 'tasks', handler: handlerA },
          { channel: 'agents', handler: handlerB },
          { channel: 'approvals', handler: handlerC },
          { channel: 'meetings', handler: handlerD },
        ],
      }),
    )

    // Wait for the effect's setup() loop to reach the registration
    // phase. The store is pre-set to ``connected: true`` so the
    // connect() step is a no-op, but subscribe() still schedules a
    // microtask pair before the handler loop starts. ``vi.waitFor``
    // polls the instrumented spy so we don't depend on a fixed
    // number of ``Promise.resolve()`` flushes -- if the hook grows
    // another await step later the test still settles correctly.
    await vi.waitFor(() => {
      // Three registrations: A, B, then C throws. D never attempts.
      expect(onChannelSpy).toHaveBeenCalledTimes(3)
    })

    unmount()

    // Exactly the handlers we registered should be deregistered --
    // no stale phantom entries for C (which threw) or D (which was
    // never attempted).
    const registeredHandlers = onChannelSpy.mock.calls
      .filter((_, idx) => idx < 2)
      .map(([, handler]) => handler)
    const deregisteredHandlers = offChannelSpy.mock.calls.map(
      ([, handler]) => handler,
    )

    expect(deregisteredHandlers).toEqual(registeredHandlers)
    expect(deregisteredHandlers).not.toContain(handlerC)
    expect(deregisteredHandlers).not.toContain(handlerD)

    // Verify the registration loop aborted after C threw: exactly
    // three onChannelEvent invocations (A, B, C) and D never
    // attempted. Without this assertion a regression that kept
    // wiring after a throw could silently register D in the store
    // even though the hook's ledger didn't record it.
    expect(onChannelSpy).toHaveBeenCalledTimes(3)
    expect(onChannelSpy).not.toHaveBeenCalledWith('meetings', handlerD)
  })
})
