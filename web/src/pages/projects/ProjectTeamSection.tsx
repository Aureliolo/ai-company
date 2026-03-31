import { Link } from 'react-router'
import { Users } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { Avatar } from '@/components/ui/avatar'
import { EmptyState } from '@/components/ui/empty-state'
import { ROUTES } from '@/router/routes'
import type { Project } from '@/api/types'

interface ProjectTeamSectionProps {
  project: Project
}

export function ProjectTeamSection({ project }: ProjectTeamSectionProps) {
  if (project.team.length === 0) {
    return (
      <SectionCard title="Team" icon={Users}>
        <EmptyState
          icon={Users}
          title="No team members"
          description="This project has no assigned team members."
        />
      </SectionCard>
    )
  }

  return (
    <SectionCard title="Team" icon={Users}>
      <div className="flex flex-col gap-2">
        {project.team.map((agentId) => (
          <Link
            key={agentId}
            to={ROUTES.AGENT_DETAIL.replace(':agentName', encodeURIComponent(agentId))}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-accent/5"
          >
            <Avatar name={agentId} />
            <span className="text-sm text-foreground">{agentId}</span>
            {agentId === project.lead && (
              <span className="ml-auto rounded-sm bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-accent">
                Lead
              </span>
            )}
          </Link>
        ))}
      </div>
    </SectionCard>
  )
}
