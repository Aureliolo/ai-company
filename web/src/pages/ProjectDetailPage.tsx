import { useParams, useNavigate } from 'react-router'
import { AlertTriangle, ArrowLeft, WifiOff } from 'lucide-react'
import { useProjectDetailData } from '@/hooks/useProjectDetailData'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ROUTES } from '@/router/routes'
import { ProjectDetailSkeleton } from './projects/ProjectDetailSkeleton'
import { ProjectHeader } from './projects/ProjectHeader'
import { ProjectTeamSection } from './projects/ProjectTeamSection'
import { ProjectTaskList } from './projects/ProjectTaskList'

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const {
    project,
    projectTasks,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useProjectDetailData(projectId ?? '')

  if (loading && !project) {
    return <ProjectDetailSkeleton />
  }

  if (!project) {
    return (
      <div className="space-y-section-gap">
        <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.PROJECTS)}>
          <ArrowLeft className="mr-1 size-4" />
          Back to Projects
        </Button>
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error ?? 'Project not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.PROJECTS)}>
        <ArrowLeft className="mr-1 size-4" />
        Back to Projects
      </Button>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning"
        >
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ErrorBoundary level="section">
        <ProjectHeader project={project} />
      </ErrorBoundary>

      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <ErrorBoundary level="section">
          <ProjectTeamSection project={project} />
        </ErrorBoundary>

        <ErrorBoundary level="section">
          <ProjectTaskList tasks={projectTasks} />
        </ErrorBoundary>
      </div>
    </div>
  )
}
