import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useArtifactsStore } from '@/stores/artifacts'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import type { Artifact, WsChannel } from '@/api/types'

const DETAIL_POLL_INTERVAL = 30_000
const WS_DEBOUNCE_MS = 300
const DETAIL_CHANNELS = ['artifacts'] as const satisfies readonly WsChannel[]
const EMPTY_BINDINGS: ChannelBinding[] = []

const EMPTY_RETURN: UseArtifactDetailDataReturn = {
  artifact: null,
  contentPreview: null,
  loading: false,
  error: null,
  wsConnected: false,
  wsSetupError: null,
}

export interface UseArtifactDetailDataReturn {
  artifact: Artifact | null
  contentPreview: string | null
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
}

export function useArtifactDetailData(artifactId: string): UseArtifactDetailDataReturn {
  const artifact = useArtifactsStore((s) => s.selectedArtifact)
  const contentPreview = useArtifactsStore((s) => s.contentPreview)
  const loading = useArtifactsStore((s) => s.detailLoading)
  const error = useArtifactsStore((s) => s.detailError)

  useEffect(() => {
    if (!artifactId) {
      useArtifactsStore.getState().clearDetail()
      return
    }
    useArtifactsStore.getState().fetchArtifactDetail(artifactId)
    return () => {
      useArtifactsStore.getState().clearDetail()
    }
  }, [artifactId])

  const pollFn = useCallback(async () => {
    if (!artifactId) return
    await useArtifactsStore.getState().fetchArtifactDetail(artifactId)
  }, [artifactId])
  const polling = usePolling(pollFn, DETAIL_POLL_INTERVAL)

  useEffect(() => {
    if (!artifactId) return
    polling.start()
    return () => polling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [artifactId])

  const wsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const artifactIdRef = useRef(artifactId)
  artifactIdRef.current = artifactId

  useEffect(() => {
    if (!artifactId && wsDebounceRef.current) {
      clearTimeout(wsDebounceRef.current)
      wsDebounceRef.current = null
    }
    return () => {
      if (wsDebounceRef.current) {
        clearTimeout(wsDebounceRef.current)
        wsDebounceRef.current = null
      }
    }
  }, [artifactId])

  const bindings: ChannelBinding[] = useMemo(
    () =>
      artifactId
        ? DETAIL_CHANNELS.map((channel) => ({
            channel,
            handler: () => {
              if (wsDebounceRef.current) clearTimeout(wsDebounceRef.current)
              wsDebounceRef.current = setTimeout(() => {
                useArtifactsStore.getState().fetchArtifactDetail(artifactIdRef.current)
              }, WS_DEBOUNCE_MS)
            },
          }))
        : EMPTY_BINDINGS,
    [artifactId],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({ bindings })

  if (!artifactId) return EMPTY_RETURN

  return { artifact, contentPreview, loading, error, wsConnected, wsSetupError }
}
