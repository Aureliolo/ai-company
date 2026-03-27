import { Link } from 'react-router'
import { Users } from 'lucide-react'
import { AgentCard } from '@/components/ui/agent-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { toRuntimeStatus } from '@/utils/agents'
import { formatRelativeTime } from '@/utils/format'
import { ROUTES } from '@/router/routes'
import { cn } from '@/lib/utils'
import type { AgentConfig } from '@/api/types'

interface AgentGridViewProps {
  agents: readonly AgentConfig[]
  className?: string
}

export function AgentGridView({ agents, className }: AgentGridViewProps) {
  if (agents.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No agents found"
        description="Try adjusting your filters or search query."
      />
    )
  }

  return (
    <StaggerGroup
      className={cn(
        'grid grid-cols-4 gap-grid-gap max-[1279px]:grid-cols-3 max-[1023px]:grid-cols-2',
        className,
      )}
    >
      {agents.map((agent) => (
        <StaggerItem key={agent.id}>
          <Link
            to={ROUTES.AGENT_DETAIL.replace(':agentName', encodeURIComponent(agent.name))}
            className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 rounded-lg"
          >
            <AgentCard
              name={agent.name}
              role={agent.role}
              department={agent.department}
              status={toRuntimeStatus(agent.status)}
              timestamp={formatRelativeTime(agent.hiring_date)}
            />
          </Link>
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
