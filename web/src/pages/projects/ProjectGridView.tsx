import { FolderKanban } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ProjectCard } from './ProjectCard'
import type { Project } from '@/api/types/projects'

interface ProjectGridViewProps {
  projects: readonly Project[]
  onToggleSelect?: (id: string) => void
  selectedIds?: ReadonlySet<string>
}

export function ProjectGridView({ projects, onToggleSelect, selectedIds }: ProjectGridViewProps) {
  if (projects.length === 0) {
    return (
      <EmptyState
        icon={FolderKanban}
        title="No projects found"
        description="Try adjusting your filters or create a new project."
      />
    )
  }

  return (
    <StaggerGroup className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 xl:grid-cols-3">
      {projects.map((project) => (
        <StaggerItem key={project.id}>
          <ProjectCard
            project={project}
            onToggleSelect={onToggleSelect}
            selected={selectedIds?.has(project.id)}
          />
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
