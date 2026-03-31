import { useCallback } from 'react'
import { useArtifactsStore } from '@/stores/artifacts'
import { useDetailData } from '@/hooks/useDetailData'
import type { Artifact, WsChannel } from '@/api/types'

const DETAIL_CHANNELS = ['artifacts'] as const satisfies readonly WsChannel[]

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

  const fetchDetail = useCallback(
    (id: string) => useArtifactsStore.getState().fetchArtifactDetail(id),
    [],
  )
  const clearDetail = useCallback(() => useArtifactsStore.getState().clearDetail(), [])

  return useDetailData({
    id: artifactId || undefined,
    fetchDetail,
    clearDetail,
    channels: DETAIL_CHANNELS,
    selectors: { artifact, contentPreview, loading, error },
  })
}
