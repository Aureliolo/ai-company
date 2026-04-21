import { useParams } from 'react-router'
import { useProjectDetailData } from '@/hooks/useProjectDetailData'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ROUTES } from '@/router/routes'
import { ProjectDetailSkeleton } from './projects/ProjectDetailSkeleton'
import { ProjectHeader } from './projects/ProjectHeader'
import { ProjectTeamSection } from './projects/ProjectTeamSection'
import { ProjectTaskList } from './projects/ProjectTaskList'

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
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
        <Breadcrumbs items={[{ label: 'Projects', to: ROUTES.PROJECTS }, { label: 'Unknown project' }]} />
        <ErrorBanner severity="error" title="Project not found" description={error ?? undefined} />
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <Breadcrumbs items={[{ label: 'Projects', to: ROUTES.PROJECTS }, { label: project.name }]} />

      {error && (
        <ErrorBanner severity="error" title="Could not load project" description={error} />
      )}

      {!wsConnected && !loading && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
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
