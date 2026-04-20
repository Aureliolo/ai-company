import { useMemo } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useTasksStore } from '@/stores/tasks'
import type { WsEvent } from '@/api/types/websocket'

/** Subscribes to the `tasks` WebSocket channel so the store receives live task updates. */
export function useTaskWebSocketUpdates() {
  const wsBindings = useMemo(
    () => [
      {
        channel: 'tasks' as const,
        handler: (event: WsEvent) => {
          useTasksStore.getState().handleWsEvent(event)
        },
      },
    ],
    [],
  )
  const { setupError } = useWebSocket({ bindings: wsBindings })
  return { setupError }
}
