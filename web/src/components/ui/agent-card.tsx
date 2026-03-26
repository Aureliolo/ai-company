import { cn, type AgentStatus } from '@/lib/utils'
import { Avatar } from './avatar'
import { StatusBadge } from './status-badge'

interface AgentCardProps {
  name: string
  role: string
  department: string
  status: AgentStatus
  currentTask?: string
  timestamp?: string
  className?: string
}

export function AgentCard({
  name,
  role,
  department,
  status,
  currentTask,
  timestamp,
  className,
}: AgentCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card p-card',
        'transition-all duration-200',
        'hover:bg-card-hover hover:-translate-y-px hover:shadow-[var(--so-shadow-card-hover)]',
        className,
      )}
    >
      {/* Header: avatar + name + status */}
      <div className="flex items-center gap-2.5">
        <Avatar name={name} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[13px] font-semibold text-foreground">
              {name}
            </span>
            <StatusBadge status={status} />
          </div>
          <span className="text-xs text-text-secondary">{role}</span>
        </div>
      </div>

      {/* Body */}
      <div className="mt-2.5 flex flex-col gap-1 border-t border-border pt-2.5">
        <div className="flex items-center gap-1 text-xs">
          <span className="text-muted-foreground">Dept:</span>
          <span className="text-text-secondary">{department}</span>
        </div>
        {currentTask && (
          <div className="flex items-center gap-1 text-xs">
            <span className="text-muted-foreground">Task:</span>
            <span className="truncate text-text-secondary">{currentTask}</span>
          </div>
        )}
        {timestamp && (
          <div className="mt-0.5 text-right">
            <span className="font-mono text-[10px] text-muted-foreground">{timestamp}</span>
          </div>
        )}
      </div>
    </div>
  )
}
