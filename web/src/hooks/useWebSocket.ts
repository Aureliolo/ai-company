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

    // The hook does NOT wrap individual store mutation calls in
    // try/catch per the project contract ("Callers MUST NOT wrap
    // store mutation calls in try/catch -- the store owns the error
    // UX"). Errors from connect/subscribe/onChannelEvent bubble to
    // the top-level ``setup().catch()`` which sets a single generic
    // ``setupError`` for the UI; the store emits toasts + logs from
    // its own mutation actions. Cancellation guards remain so a
    // stale effect cannot register handlers against a newer mount.
    const setup = async () => {
      setSetupError(null)
      if (!wsStore.connected) {
        await wsStore.connect()
      }
      if (cancelled) return

      wsStore.subscribe(uniqueChannels, filters)
      subscribed = true
      if (cancelled) return

      // Push to the ledger AFTER the call succeeds so a throw from
      // ``onChannelEvent`` naturally aborts the loop without leaving
      // the failed binding in the rollback ledger. The outer
      // ``setup().catch()`` records the failure in setupError.
      for (const binding of bindings) {
        if (cancelled) return
        wsStore.onChannelEvent(binding.channel, binding.handler)
        registered.push(binding)
      }
    }

    setup().catch((err) => {
      if (!cancelled) {
        setSetupError('WebSocket setup failed.')
      }
      log.error('Setup failed:', err)
    })

    return () => {
      cancelled = true
      // Cleanup also delegates error UX to the store. ``for`` loop
      // survives a throw from any single ``offChannelEvent`` because
      // the store's own error handling records it -- however, since
      // cleanup runs synchronously under React's unmount and a store
      // throw here WOULD skip subsequent ``offChannelEvent`` / the
      // final ``unsubscribe``, we keep *only* a minimal try/catch
      // around each individual call so per-binding failures cannot
      // leave stale channel subscriptions behind. This is the same
      // "best-effort cleanup" carve-out that ``_nats_consumers``
      // uses on the Python side.
      for (const binding of registered) {
        try {
          wsStore.offChannelEvent(binding.channel, binding.handler)
        } catch (err) {
          log.error('Handler cleanup failed:', err)
        }
      }
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
