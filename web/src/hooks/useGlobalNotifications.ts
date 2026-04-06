import { useEffect, useMemo, useRef } from 'react'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { useAgentsStore } from '@/stores/agents'
import { useToastStore } from '@/stores/toast'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import type { WsChannel } from '@/api/types'

const log = createLogger('useGlobalNotifications')

/**
 * Subscribe globally to WebSocket channels that drive app-wide notifications.
 *
 * Mounted once at the {@link AppLayout} level so notifications render regardless
 * of which page the user is currently viewing. Dispatches events to the stores
 * that own the user-facing behaviour (e.g. the agents store forwards
 * `personality.trimmed` events to the toast queue).
 *
 * Connection failures surface to the user via toast notifications so a silent
 * WebSocket death does not leave users wondering why toasts stopped arriving.
 *
 * This hook is intentionally minimal -- it only covers *global* notifications.
 * Page-scoped WebSocket handling remains in the per-page data hooks.
 */
const GLOBAL_CHANNELS = ['agents'] as const satisfies readonly WsChannel[]

export function useGlobalNotifications(): void {
  const bindings: ChannelBinding[] = useMemo(
    () =>
      GLOBAL_CHANNELS.map((channel) => ({
        channel,
        handler: (event) => {
          try {
            useAgentsStore.getState().updateFromWsEvent(event)
          } catch (err) {
            log.warn('updateFromWsEvent threw -- event dropped', { event_type: sanitizeForLog(event?.event_type) }, err)
          }
        },
      })),
    [],
  )

  const { setupError, reconnectExhausted, connected } = useWebSocket({ bindings })

  // Surface setup errors via a one-time warning toast. Without this, a failed
  // WS connection silently kills the entire global notifications pipeline.
  const lastSetupErrorRef = useRef<string | null>(null)
  useEffect(() => {
    if (setupError && setupError !== lastSetupErrorRef.current) {
      lastSetupErrorRef.current = setupError
      // `setupError` originates from WebSocket transport errors, which can
      // surface messages derived from untrusted response bodies; sanitize
      // before embedding in the structured log.
      log.warn('Global notifications WebSocket setup failed', {
        setupError: sanitizeForLog(setupError),
      })
      useToastStore.getState().add({
        variant: 'warning',
        title: 'Live notifications unavailable',
        description: 'You may miss real-time updates. Try refreshing the page.',
      })
    }
  }, [setupError])

  // Surface reconnect exhaustion as a more severe error toast -- the WS is
  // permanently dead until the user refreshes.
  const reconnectExhaustedRef = useRef(false)
  useEffect(() => {
    if (reconnectExhausted && !reconnectExhaustedRef.current) {
      reconnectExhaustedRef.current = true
      log.error('Global notifications reconnect exhausted')
      useToastStore.getState().add({
        variant: 'error',
        title: 'Live notifications disconnected',
        description: 'Reconnect attempts exhausted. Refresh to restore.',
      })
    }
  }, [reconnectExhausted])

  // Reset the one-shot refs when the WS successfully reconnects so a flapping
  // connection (transient network loss, backend restart) can emit a fresh
  // toast on the next failure instead of staying silent forever.
  useEffect(() => {
    if (connected) {
      reconnectExhaustedRef.current = false
      lastSetupErrorRef.current = null
    }
  }, [connected])
}
