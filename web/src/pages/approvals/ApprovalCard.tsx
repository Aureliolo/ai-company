import { useEffect, useRef, useState } from 'react'
import { Check, Clock, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useFlash } from '@/hooks/useFlash'
import { formatUrgency, getRiskLevelColor, getRiskLevelLabel, getUrgencyColor } from '@/utils/approvals'
import type { ApprovalResponse } from '@/api/types'

export interface ApprovalCardProps {
  approval: ApprovalResponse
  selected: boolean
  onSelect: (id: string) => void
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onToggleSelect: (id: string) => void
  className?: string
}

const DOT_COLOR_CLASSES: Record<string, string> = {
  danger: 'bg-danger',
  warning: 'bg-warning',
  accent: 'bg-accent',
  'accent-dim': 'bg-accent-dim',
}

const URGENCY_BADGE_CLASSES: Record<string, string> = {
  danger: 'border-danger/30 bg-danger/10 text-danger',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  accent: 'border-accent/30 bg-accent/10 text-accent',
  'text-secondary': 'border-border bg-surface text-text-secondary',
}

export function ApprovalCard({
  approval,
  selected,
  onSelect,
  onApprove,
  onReject,
  onToggleSelect,
  className,
}: ApprovalCardProps) {
  const riskColor = getRiskLevelColor(approval.risk_level)
  const urgencyColor = getUrgencyColor(approval.urgency_level)
  const isPending = approval.status === 'pending'

  // Flash on status change
  const { flashStyle, triggerFlash } = useFlash()
  const prevStatusRef = useRef(approval.status)
  useEffect(() => {
    if (approval.status !== prevStatusRef.current) {
      triggerFlash()
      prevStatusRef.current = approval.status
    }
  }, [approval.status, triggerFlash])

  // Local countdown -- tracks seconds_remaining with a 1s tick
  const [countdown, setCountdown] = useState(approval.seconds_remaining)
  const prevSecondsRef = useRef(approval.seconds_remaining)
  if (approval.seconds_remaining !== prevSecondsRef.current) {
    prevSecondsRef.current = approval.seconds_remaining
    setCountdown(approval.seconds_remaining)
  }

  useEffect(() => {
    if (countdown === null || countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) return 0
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown !== null && countdown > 0]) // eslint-disable-line @eslint-react/exhaustive-deps

  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-4 transition-all duration-200',
        selected ? 'border-bright ring-1 ring-accent/20' : 'border-border',
        isPending && 'hover:bg-card-hover hover:-translate-y-px hover:shadow-md',
        !isPending && 'opacity-70',
        className,
      )}
      style={flashStyle}
      role="article"
      aria-label={`Approval: ${approval.title}`}
    >
      {/* Header row */}
      <div className="flex items-start gap-3">
        {/* Checkbox (only for pending) */}
        {isPending && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(approval.id)}
            className="mt-1 size-4 shrink-0 accent-accent"
            aria-label={`Select ${approval.title}`}
          />
        )}

        {/* Risk dot */}
        <span
          className={cn(
            'mt-1.5 size-2 shrink-0 rounded-full',
            DOT_COLOR_CLASSES[riskColor],
            approval.urgency_level === 'critical' && isPending && 'animate-pulse',
          )}
          aria-label={`Risk: ${getRiskLevelLabel(approval.risk_level)}`}
        />

        {/* Content */}
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => onSelect(approval.id)}
            className="text-left text-sm font-medium text-foreground hover:text-accent transition-colors truncate block w-full"
          >
            {approval.title}
          </button>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
            <span className="font-mono">{approval.action_type}</span>
            <span aria-hidden="true">--</span>
            <span>{approval.requested_by}</span>
          </div>
        </div>

        {/* Urgency badge */}
        {isPending && countdown !== null && (
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] font-medium shrink-0',
              URGENCY_BADGE_CLASSES[urgencyColor],
            )}
            aria-hidden="true"
          >
            <Clock className="size-3" aria-hidden="true" />
            {formatUrgency(countdown)}
          </span>
        )}

        {isPending && countdown === null && (
          <span className="text-[11px] text-text-muted shrink-0">No expiry</span>
        )}
      </div>

      {/* Action buttons (pending only) */}
      {isPending && (
        <div className="mt-3 flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 border-success/30 text-success hover:bg-success/10"
            onClick={() => onApprove(approval.id)}
          >
            <Check className="size-3.5" />
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 border-danger/30 text-danger hover:bg-danger/10"
            onClick={() => onReject(approval.id)}
          >
            <X className="size-3.5" />
            Reject
          </Button>
        </div>
      )}
    </div>
  )
}
