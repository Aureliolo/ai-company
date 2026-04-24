import { useEffect, useState } from 'react'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/lib/logger'
import type { WsChannel, WsEventHandler, WsSubscriptionFilters } from '@/api/types/websocket'

const log = createLogger('useWebSocket')

/** A binding from a WebSocket channel to an event handler. */
export interface ChannelBinding {
  readonly channel: WsChannel
  readonly handler: WsEventHandler
}

/** Options for the useWebSocket hook. */
export interface WebSocketOptions {
  /** Channel-to-handler bindings. Each channel will be subscribed and its handler wired. */
  readonly bindings: readonly ChannelBinding[]
  /** Optional filters passed to wsStore.subscribe(). */
  readonly filters?: WsSubscriptionFilters
  /** Whether WebSocket should be active. Defaults to checking auth status. */
  readonly enabled?: boolean
}

/** Return type exposing WebSocket connection and setup status. */
export interface WebSocketReturn {
  /** Whether the WebSocket is currently connected. */
  readonly connected: boolean
  /** Whether reconnection attempts have been exhausted. */
  readonly reconnectExhausted: boolean
  /** Non-null when WebSocket setup failed (connect or subscribe error). */
  readonly setupError: string | null
}

/**
 * Manage WebSocket subscription lifecycle for a page view.
 *
 * Connects when enabled (default: authenticated session), subscribes to
 * deduplicated channels, and wires event handlers on mount. Automatically
 * unsubscribes and removes handlers on unmount.
 *
 * **Important:** The `bindings` and `filters` are only processed on mount
 * (or when `enabled` changes from false to true). If they need to change
 * dynamically, the consuming component must be remounted, for example by
 * changing its `key` prop.
 */
export function useWebSocket(options: WebSocketOptions): WebSocketReturn {
  const { bindings, filters, enabled } = options
  const authStatus = useAuthStore((s) => s.authStatus)
  const connected = useWebSocketStore((s) => s.connected)
  const reconnectExhausted = useWebSocketStore((s) => s.reconnectExhausted)
  const [setupError, setSetupError] = useState<string | null>(null)

  const isEnabled = enabled !== undefined ? enabled : authStatus === 'authenticated'

  useEffect(() => {
    if (!isEnabled) return

    const wsStore = useWebSocketStore.getState()
    const uniqueChannels: WsChannel[] = [...new Set(bindings.map((b) => b.channel))]

    // Effect-local cancellation token. Captured by async closures
    // below so a stale setup() from a previous `enabled` toggle
    // cannot register handlers into a newer effect's ledger after
    // its cleanup already ran. A shared ref would let stale tasks
    // race across mounts.
    let cancelled = false

    // List of (channel, handler) pairs wired by this effect instance.
    // Declared before `setup()` so the declaration precedes all reads;
    // populated during setup and iterated by the cleanup callback.
    // Kept local to the effect so each mount owns its registration
    // ledger.
    const registered: Array<ChannelBinding> = []

    // Flip to true after wsStore.subscribe() succeeds so cleanup knows
    // whether there are channel subscriptions to tear down. Channel
    // subscriptions are separate from per-handler registrations; the
    // hook owns both and must unwind both on unmount.
    let subscribed = false

    const setup = async () => {
      // Clear any stale error from a previous failed setup
      setSetupError(null)
      try {
        if (!wsStore.connected) {
          await wsStore.connect()
        }
      } catch (err) {
        if (cancelled) return
        setSetupError('WebSocket connection failed.')
        log.error('Connect failed:', err)
        return
      }

      if (cancelled) return

      try {
        wsStore.subscribe(uniqueChannels, filters)
        subscribed = true
      } catch (err) {
        setSetupError('WebSocket subscription failed.')
        log.error('Subscribe failed:', err)
        return
      }

      if (cancelled) return

      // Track which (channel, handler) pairs we successfully register
      // so cleanup can roll back ONLY those -- if setup throws
      // mid-loop, we must not try to deregister bindings that were
      // never wired.
      for (const binding of bindings) {
        if (cancelled) return
        try {
          wsStore.onChannelEvent(binding.channel, binding.handler)
          registered.push(binding)
        } catch (err) {
          setSetupError('WebSocket handler setup failed.')
          log.error('Handler wiring failed:', err)
          // Stop wiring further bindings -- cleanup will roll back
          // the ones we already registered via the `registered` list.
          return
        }
      }
    }

    setup().catch((err) => {
      if (!cancelled) {
        setSetupError('WebSocket setup failed unexpectedly.')
      }
      log.error('Setup failed:', err)
    })

    return () => {
      cancelled = true
      // Only remove handlers we actually registered -- do NOT iterate
      // the full bindings list because a mid-loop throw may have left
      // later bindings unregistered. The store's handler set
      // deduplication ensures cleanup is safe per-handler; symmetry
      // here prevents stale phantom cleanups across reconnects.
      for (const binding of registered) {
        try {
          wsStore.offChannelEvent(binding.channel, binding.handler)
        } catch (err) {
          log.error('Handler cleanup failed:', err)
        }
      }
      // Unsubscribe from the channel subscriptions we created. Without
      // this the store keeps routing broadcast traffic to channels
      // the page no longer renders, leaking subscription state across
      // mounts (and eventually across reconnects that refresh the
      // subscribedChannels array).
      if (subscribed) {
        try {
          wsStore.unsubscribe(uniqueChannels)
        } catch (err) {
          log.error('Unsubscribe failed:', err)
        }
      }
    }
    // Bindings and filters are intentionally excluded -- they are captured
    // once on mount and remain stable for the component's lifetime. Changing
    // them requires remounting the component (e.g. via a key prop).
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [isEnabled])

  return { connected, reconnectExhausted, setupError }
}
