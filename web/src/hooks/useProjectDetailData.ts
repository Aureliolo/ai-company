import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useProjectsStore } from '@/stores/projects'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import type { Project, Task, WsChannel } from '@/api/types'

const DETAIL_POLL_INTERVAL = 30_000
const WS_DEBOUNCE_MS = 300
const DETAIL_CHANNELS = ['projects', 'tasks'] as const satisfies readonly WsChannel[]
const EMPTY_BINDINGS: ChannelBinding[] = []

const EMPTY_RETURN: UseProjectDetailDataReturn = {
  project: null,
  projectTasks: [],
  loading: false,
  error: null,
  wsConnected: false,
  wsSetupError: null,
}

export interface UseProjectDetailDataReturn {
  project: Project | null
  projectTasks: readonly Task[]
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
}

export function useProjectDetailData(projectId: string): UseProjectDetailDataReturn {
  const project = useProjectsStore((s) => s.selectedProject)
  const projectTasks = useProjectsStore((s) => s.projectTasks)
  const loading = useProjectsStore((s) => s.detailLoading)
  const error = useProjectsStore((s) => s.detailError)

  useEffect(() => {
    if (!projectId) {
      useProjectsStore.getState().clearDetail()
      return
    }
    useProjectsStore.getState().fetchProjectDetail(projectId)
    return () => {
      useProjectsStore.getState().clearDetail()
    }
  }, [projectId])

  const pollFn = useCallback(async () => {
    if (!projectId) return
    await useProjectsStore.getState().fetchProjectDetail(projectId)
  }, [projectId])
  const polling = usePolling(pollFn, DETAIL_POLL_INTERVAL)

  useEffect(() => {
    if (!projectId) return
    polling.start()
    return () => polling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [projectId])

  const wsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const projectIdRef = useRef(projectId)
  projectIdRef.current = projectId

  useEffect(() => {
    if (!projectId && wsDebounceRef.current) {
      clearTimeout(wsDebounceRef.current)
      wsDebounceRef.current = null
    }
    return () => {
      if (wsDebounceRef.current) {
        clearTimeout(wsDebounceRef.current)
        wsDebounceRef.current = null
      }
    }
  }, [projectId])

  const bindings: ChannelBinding[] = useMemo(
    () =>
      projectId
        ? DETAIL_CHANNELS.map((channel) => ({
            channel,
            handler: () => {
              if (wsDebounceRef.current) clearTimeout(wsDebounceRef.current)
              wsDebounceRef.current = setTimeout(() => {
                useProjectsStore.getState().fetchProjectDetail(projectIdRef.current)
              }, WS_DEBOUNCE_MS)
            },
          }))
        : EMPTY_BINDINGS,
    [projectId],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({ bindings })

  if (!projectId) return EMPTY_RETURN

  return { project, projectTasks, loading, error, wsConnected, wsSetupError }
}
