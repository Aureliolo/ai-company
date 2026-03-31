import { useState } from 'react'
import { AlertTriangle, Plus, WifiOff } from 'lucide-react'
import { useProjectsData } from '@/hooks/useProjectsData'
import { Button } from '@/components/ui/button'
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
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Projects</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {filteredProjects.length} of {totalProjects}
          </span>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 size-4" />
            Create Project
          </Button>
        </div>
      </div>

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

      <ProjectFilters />
      <ProjectGridView projects={filteredProjects} />

      <ProjectCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
