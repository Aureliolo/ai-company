import { useCallback } from 'react'
import { useProjectsStore } from '@/stores/projects'
import { useDetailData } from '@/hooks/useDetailData'
import type { Project, Task, WsChannel } from '@/api/types'

const DETAIL_CHANNELS = ['projects', 'tasks'] as const satisfies readonly WsChannel[]

export interface UseProjectDetailDataReturn {
  project: Project | null
  projectTasks: readonly Task[]
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
}

export function useProjectDetailData(projectId: string | undefined): UseProjectDetailDataReturn {
  const project = useProjectsStore((s) => s.selectedProject)
  const projectTasks = useProjectsStore((s) => s.projectTasks)
  const loading = useProjectsStore((s) => s.detailLoading)
  const error = useProjectsStore((s) => s.detailError)

  const fetchDetail = useCallback(
    (id: string) => useProjectsStore.getState().fetchProjectDetail(id),
    [],
  )
  const clearDetail = useCallback(() => useProjectsStore.getState().clearDetail(), [])

  return useDetailData({
    id: projectId || undefined,
    fetchDetail,
    clearDetail,
    channels: DETAIL_CHANNELS,
    selectors: { project, projectTasks, loading, error },
  })
}
