import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useProjectsData } from '@/hooks/useProjectsData'
import { Button } from '@/components/ui/button'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
import { ProjectsSkeleton } from './projects/ProjectsSkeleton'
import { ProjectFilters } from './projects/ProjectFilters'
import { ProjectGridView } from './projects/ProjectGridView'
import { ProjectCreateDrawer } from './projects/ProjectCreateDrawer'

export default function ProjectsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const {
    filteredProjects,
    totalProjects,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useProjectsData()

  if (loading && totalProjects === 0) {
    return <ProjectsSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <ListHeader
        title="Projects"
        count={filteredProjects.length}
        countLabel={filteredProjects.length === totalProjects ? undefined : `${filteredProjects.length} of ${totalProjects}`}
        primaryAction={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" />
            New project
          </Button>
        }
      />

      {error && (
        <ErrorBanner severity="error" title="Could not load projects" description={error} />
      )}

      {!wsConnected && !loading && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
      )}

      <ProjectFilters />
      <ProjectGridView projects={filteredProjects} />

      <ProjectCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
