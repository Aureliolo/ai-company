import { FolderKanban } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ProjectCard } from './ProjectCard'
import type { Project } from '@/api/types'

interface ProjectGridViewProps {
  projects: readonly Project[]
}

export function ProjectGridView({ projects }: ProjectGridViewProps) {
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
    <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[1279px]:grid-cols-2 max-[767px]:grid-cols-1">
      {projects.map((project) => (
        <StaggerItem key={project.id}>
          <ProjectCard project={project} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
