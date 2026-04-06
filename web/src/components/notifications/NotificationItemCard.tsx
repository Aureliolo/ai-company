import { AlertTriangle, Check, Info, X, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router'

import { cn } from '@/lib/utils'
import type { NotificationItem, NotificationSeverity } from '@/types/notifications'

const SEVERITY_ICONS: Record<NotificationSeverity, React.ElementType> = {
  info: Info,
  warning: AlertTriangle,
  error: XCircle,
  critical: XCircle,
}

const SEVERITY_COLORS: Record<NotificationSeverity, string> = {
  info: 'text-accent',
  warning: 'text-warning',
  error: 'text-danger',
  critical: 'text-danger',
}

const BORDER_COLORS: Record<NotificationSeverity, string> = {
  info: 'border-l-accent',
  warning: 'border-l-warning',
  error: 'border-l-danger',
  critical: 'border-l-danger',
}

function formatRelativeTime(timestamp: string): string {
  const ts = new Date(timestamp).getTime()
  if (Number.isNaN(ts)) return 'just now'
  const diff = Math.max(0, Date.now() - ts)
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

interface NotificationItemCardProps {
  readonly item: NotificationItem
  readonly onMarkRead: (id: string) => void
  readonly onDismiss: (id: string) => void
}

export function NotificationItemCard({
  item,
  onMarkRead,
  onDismiss,
}: NotificationItemCardProps) {
  const navigate = useNavigate()
  const Icon = SEVERITY_ICONS[item.severity]

  function handleClick() {
    if (!item.read) onMarkRead(item.id)
    if (item.href && item.href.startsWith('/') && !item.href.startsWith('//')) {
      void navigate(item.href)
    }
  }

  return (
    <div
      role="listitem"
      tabIndex={0}
      aria-label={`${item.severity} notification: ${item.title}`}
      className={cn(
        'group relative flex w-full gap-3 rounded-md border-l-2 px-3 py-2 text-left',
        'transition-colors hover:bg-card-hover',
        item.read ? 'border-l-transparent' : BORDER_COLORS[item.severity],
        !item.read && 'bg-accent/5',
        item.href && 'cursor-pointer',
      )}
      onClick={handleClick}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !(e.target as HTMLElement).closest('button')) {
          e.preventDefault()
          handleClick()
        }
      }}
    >
      <Icon className={cn('mt-0.5 size-4 shrink-0', SEVERITY_COLORS[item.severity])} />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{item.title}</p>
        {item.description && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {item.description}
          </p>
        )}
        <p className="mt-1 text-xs text-muted-foreground/70">
          {formatRelativeTime(item.timestamp)}
        </p>
      </div>

      <div className="flex shrink-0 items-start gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        {!item.read && (
          <button
            type="button"
            className="rounded p-0.5 text-muted-foreground hover:bg-accent/10 hover:text-accent"
            aria-label="Mark as read"
            title="Mark as read"
            onClick={(e) => {
              e.stopPropagation()
              onMarkRead(item.id)
            }}
          >
            <Check className="size-3.5" />
          </button>
        )}
        <button
          type="button"
          className="rounded p-0.5 text-muted-foreground hover:bg-danger/10 hover:text-danger"
          aria-label="Dismiss notification"
          title="Dismiss"
          onClick={(e) => {
            e.stopPropagation()
            onDismiss(item.id)
          }}
        >
          <X className="size-3.5" />
        </button>
      </div>
    </div>
  )
}
