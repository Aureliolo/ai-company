import { useMemo } from 'react'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { useAgentsStore } from '@/stores/agents'
import type { WsChannel } from '@/api/types'

/**
 * Subscribe globally to WebSocket channels that drive app-wide notifications.
 *
 * Mounted once at the {@link AppLayout} level so notifications render regardless
 * of which page the user is currently viewing. Dispatches events to the stores
 * that own the user-facing behaviour (e.g. the agents store forwards
 * `personality.trimmed` events to the toast queue).
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
          useAgentsStore.getState().updateFromWsEvent(event)
        },
      })),
    [],
  )

  useWebSocket({ bindings })
}
