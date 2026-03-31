import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import type { WsChannel } from '@/api/types'

const DETAIL_POLL_INTERVAL = 30_000
const WS_DEBOUNCE_MS = 300
const EMPTY_BINDINGS: ChannelBinding[] = []

export interface DetailDataConfig<T> {
  /** The entity ID to fetch (undefined/empty = inactive). */
  id: string | undefined
  /** Fetches detail data for the given ID. */
  fetchDetail: (id: string) => Promise<void>
  /** Clears detail state in the store. */
  clearDetail: () => void
  /** WS channels to subscribe to for live updates. */
  channels: readonly WsChannel[]
  /** Store selectors for the return value. */
  selectors: T
}

export interface DetailDataBase {
  wsConnected: boolean
  wsSetupError: string | null
}

/**
 * Shared logic for detail page data hooks: initial fetch, polling, WS debounce,
 * and cleanup. Returns the provided selectors merged with WS connection state.
 */
export function useDetailData<T>(config: DetailDataConfig<T>): T & DetailDataBase {
  const { id, fetchDetail, clearDetail, channels, selectors } = config

  useEffect(() => {
    if (!id) {
      clearDetail()
      return
    }
    fetchDetail(id)
    return () => {
      clearDetail()
    }
  }, [id, fetchDetail, clearDetail])

  const pollFn = useCallback(async () => {
    if (!id) return
    await fetchDetail(id)
  }, [id, fetchDetail])
  const polling = usePolling(pollFn, DETAIL_POLL_INTERVAL)

  useEffect(() => {
    if (!id) return
    polling.start()
    return () => polling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps -- polling object is stable (memoized by usePolling)
  }, [id])

  const wsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const idRef = useRef(id)
  idRef.current = id

  useEffect(() => {
    if (!id && wsDebounceRef.current) {
      clearTimeout(wsDebounceRef.current)
      wsDebounceRef.current = null
    }
    return () => {
      if (wsDebounceRef.current) {
        clearTimeout(wsDebounceRef.current)
        wsDebounceRef.current = null
      }
    }
  }, [id])

  const bindings: ChannelBinding[] = useMemo(
    () =>
      id
        ? channels.map((channel) => ({
            channel,
            handler: () => {
              if (wsDebounceRef.current) clearTimeout(wsDebounceRef.current)
              wsDebounceRef.current = setTimeout(() => {
                const currentId = idRef.current
                if (currentId) fetchDetail(currentId)
              }, WS_DEBOUNCE_MS)
            },
          }))
        : EMPTY_BINDINGS,
    [id, channels, fetchDetail],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({ bindings })

  return { ...selectors, wsConnected, wsSetupError }
}
