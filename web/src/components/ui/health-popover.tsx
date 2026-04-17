import { Dialog } from '@base-ui/react/dialog'
import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock,
  Database,
  Loader2,
  RefreshCw,
  Tag,
  Waves,
  Wifi,
  X,
  XCircle,
  Zap,
} from 'lucide-react'
import { getHealth } from '@/api/endpoints/health'
import { useWebSocketStore } from '@/stores/websocket'
import { createLogger } from '@/lib/logger'
import { formatTime } from '@/utils/format'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { HealthStatus } from '@/api/types'

const log = createLogger('HealthDialog')

type LoadState =
  | { state: 'idle' }
  | { state: 'loading' }
  | { state: 'ok'; data: HealthStatus; fetchedAt: Date }
  | { state: 'error'; message: string; fetchedAt: Date }

type SubsystemState = 'ok' | 'degraded' | 'down' | 'unknown' | 'loading'

function formatUptime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return 'unknown'
  const days = Math.floor(seconds / 86_400)
  const hours = Math.floor((seconds % 86_400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

/** Render an ISO-delta as a compact relative phrase ("just now", "5s ago", "2m ago"...). */
function formatRelative(fromMs: number, nowMs: number): string {
  const diffSec = Math.max(0, Math.round((nowMs - fromMs) / 1000))
  if (diffSec < 2) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) {
    const remSec = diffSec % 60
    return remSec === 0 ? `${diffMin}m ago` : `${diffMin}m ${remSec}s ago`
  }
  const diffHour = Math.floor(diffMin / 60)
  const remMin = diffMin % 60
  return remMin === 0 ? `${diffHour}h ago` : `${diffHour}h ${remMin}m ago`
}

const STATE_META: Record<SubsystemState, { label: string; textClass: string; borderClass: string; bgClass: string }> = {
  ok: {
    label: 'Operational',
    textClass: 'text-success',
    borderClass: 'border-success/40',
    bgClass: 'bg-success/5',
  },
  degraded: {
    label: 'Degraded',
    textClass: 'text-warning',
    borderClass: 'border-warning/40',
    bgClass: 'bg-warning/5',
  },
  down: {
    label: 'Down',
    textClass: 'text-danger',
    borderClass: 'border-danger/40',
    bgClass: 'bg-danger/5',
  },
  unknown: {
    label: 'Unknown',
    textClass: 'text-muted-foreground',
    borderClass: 'border-border',
    bgClass: 'bg-card',
  },
  loading: {
    label: 'Checking...',
    textClass: 'text-muted-foreground',
    borderClass: 'border-border',
    bgClass: 'bg-card',
  },
}

function StateIcon({ state, className }: { state: SubsystemState; className?: string }) {
  const cls = cn('size-5 shrink-0', className)
  if (state === 'ok') return <CheckCircle2 className={cn(cls, 'text-success')} aria-hidden="true" />
  if (state === 'degraded') return <AlertTriangle className={cn(cls, 'text-warning')} aria-hidden="true" />
  if (state === 'down') return <XCircle className={cn(cls, 'text-danger')} aria-hidden="true" />
  if (state === 'loading') return <Loader2 className={cn(cls, 'animate-spin text-muted-foreground')} aria-hidden="true" />
  return <CircleHelp className={cn(cls, 'text-muted-foreground')} aria-hidden="true" />
}

interface SubsystemCardProps {
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>
  label: string
  description: string
  state: SubsystemState
  detail?: string
}

function SubsystemCard({ icon: Icon, label, description, state, detail }: SubsystemCardProps) {
  const meta = STATE_META[state]
  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-lg border p-card transition-colors',
        meta.borderClass,
        meta.bgClass,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Icon className="size-4 text-muted-foreground" aria-hidden={true} />
          <span className="text-sm font-semibold text-foreground">{label}</span>
        </div>
        <StateIcon state={state} />
      </div>
      <p className="text-compact text-muted-foreground">{description}</p>
      <div className="mt-auto flex items-baseline justify-between gap-2 pt-1">
        <span className={cn('text-sm font-semibold', meta.textClass)}>{meta.label}</span>
        {detail && (
          <span className="text-compact text-muted-foreground">{detail}</span>
        )}
      </div>
    </div>
  )
}

function HeroStatus({ state }: { state: SubsystemState }) {
  const meta = STATE_META[state]
  const headline: Record<SubsystemState, string> = {
    ok: 'All systems operational',
    degraded: 'Some subsystems degraded',
    down: 'Backend unreachable',
    unknown: 'Status unknown',
    loading: 'Checking system health...',
  }
  const sub: Record<SubsystemState, string> = {
    ok: 'Every tracked component is reporting healthy.',
    degraded: 'One or more subsystems are not fully operational. Check the cards below.',
    down: 'The backend API is not responding. Live data may be stale.',
    unknown: 'No recent health snapshot. Waiting for the first probe to complete.',
    loading: 'Fetching the latest snapshot from the backend.',
  }
  return (
    <div
      className={cn(
        'flex items-center gap-4 rounded-xl border p-card',
        meta.borderClass,
        meta.bgClass,
      )}
    >
      <StateIcon state={state} className="size-10" />
      <div className="flex-1">
        <div className={cn('text-lg font-semibold', meta.textClass)}>{headline[state]}</div>
        <p className="text-sm text-muted-foreground">{sub[state]}</p>
      </div>
    </div>
  )
}

export interface HealthPopoverProps {
  /** The trigger element -- cloned into `Dialog.Trigger render`. */
  children: ReactElement
}

/**
 * Shared health-status modal dialog used by both the StatusBar "all
 * systems normal" pill and the Sidebar "Connected" indicator.  A fresh
 * ``/health`` snapshot is fetched each time the dialog opens (and on
 * demand via the refresh button), combined with the live WebSocket
 * connection state from ``useWebSocketStore``, and rendered as a
 * centered modal covering ~70% of the viewport at laptop sizes.
 *
 * The trigger is provided by the caller (any existing visual) via the
 * `children` prop; this component handles the Dialog shell, the
 * fetching, and the rendered health-screen content.
 */
export function HealthPopover({ children }: HealthPopoverProps) {
  const [open, setOpen] = useState(false)
  const [loadState, setLoadState] = useState<LoadState>({ state: 'idle' })
  const [nowMs, setNowMs] = useState(() => Date.now())
  const wsConnected = useWebSocketStore((s) => s.connected)
  const wsReconnectExhausted = useWebSocketStore((s) => s.reconnectExhausted)

  // Live-updating "X seconds ago" ticker. Starts when the dialog opens,
  // stops when it closes, so we never hold a background timer for a
  // closed modal.  1-second cadence is fine at this scale -- the dialog
  // shows at most 4 subsystem cards and a small metadata block.
  useEffect(() => {
    if (!open) return
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [open])

  // Fetch on demand.  Called from the dialog's onOpenChange handler and
  // from the refresh button -- deliberately NOT inside a useEffect, so
  // the state update is always a response to a user interaction rather
  // than a render-triggered side effect.
  const latestProbeRef = useRef(0)

  const fetchHealth = useCallback(() => {
    setLoadState({ state: 'loading' })
    const probeId = ++latestProbeRef.current
    getHealth()
      .then((data) => {
        if (probeId !== latestProbeRef.current) return
        const fetchedAt = new Date()
        setLoadState({ state: 'ok', data, fetchedAt })
        setNowMs(fetchedAt.getTime())
      })
      .catch((err: unknown) => {
        if (probeId !== latestProbeRef.current) return
        const fetchedAt = new Date()
        const message = err instanceof Error ? err.message : 'Health probe failed'
        log.warn('Health probe failed', err)
        setLoadState({ state: 'error', message, fetchedAt })
        setNowMs(fetchedAt.getTime())
      })
  }, [])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen)
      if (nextOpen) {
        fetchHealth()
      }
    },
    [fetchHealth],
  )

  // Derive individual subsystem states
  const apiState: SubsystemState =
    loadState.state === 'loading'
      ? 'loading'
      : loadState.state === 'ok'
        ? loadState.data.status
        : loadState.state === 'error'
          ? 'down'
          : 'unknown'

  const wsState: SubsystemState = wsConnected
    ? 'ok'
    : wsReconnectExhausted
      ? 'down'
      : loadState.state === 'loading'
        ? 'loading'
        : 'degraded'

  const wsDetail = wsConnected
    ? undefined
    : wsReconnectExhausted
      ? 'reconnect budget exhausted'
      : 'auto-reconnecting'

  const persistenceState: SubsystemState =
    loadState.state === 'loading'
      ? 'loading'
      : loadState.state === 'ok'
        ? loadState.data.persistence === true
          ? 'ok'
          : loadState.data.persistence === false
            ? 'down'
            : 'unknown'
        : 'unknown'

  const busState: SubsystemState =
    loadState.state === 'loading'
      ? 'loading'
      : loadState.state === 'ok'
        ? loadState.data.message_bus === true
          ? 'ok'
          : loadState.data.message_bus === false
            ? 'down'
            : 'unknown'
        : 'unknown'

  // Overall status -- worst wins
  const overallState: SubsystemState = (() => {
    const states: SubsystemState[] = [apiState, wsState, persistenceState, busState]
    if (states.includes('down')) return 'down'
    if (states.includes('degraded')) return 'degraded'
    if (states.includes('loading')) return 'loading'
    if (states.includes('unknown')) return 'unknown'
    return 'ok'
  })()

  const fetchedAtLabel =
    loadState.state === 'ok' || loadState.state === 'error'
      ? `${formatTime(loadState.fetchedAt.toISOString())} (${formatRelative(loadState.fetchedAt.getTime(), nowMs)})`
      : null

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Trigger render={children} />
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />
        <Dialog.Popup
          className={cn(
            'fixed left-1/2 top-1/2 z-50 w-full max-w-3xl -translate-x-1/2 -translate-y-1/2',
            'max-h-[85vh] overflow-y-auto',
            'rounded-xl border border-border-bright bg-surface p-card shadow-[var(--so-shadow-card-hover)]',
            'transition-[opacity,translate,scale] duration-200 ease-out',
            'data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
            'data-[closed]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:scale-95',
          )}
        >
          {/* Header */}
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <Dialog.Title className="text-lg font-semibold text-foreground">
                System Health
              </Dialog.Title>
              <Dialog.Description className="text-compact text-muted-foreground">
                Live snapshot of the SynthOrg backend subsystems.
              </Dialog.Description>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Refresh health snapshot"
                onClick={fetchHealth}
                disabled={loadState.state === 'loading'}
                title="Refresh"
              >
                <RefreshCw
                  className={cn(
                    'size-4',
                    loadState.state === 'loading' && 'animate-spin',
                  )}
                />
              </Button>
              <Dialog.Close
                render={
                  <Button variant="ghost" size="icon" type="button" aria-label="Close">
                    <X className="size-4" />
                  </Button>
                }
              />
            </div>
          </div>

          {/* Hero status */}
          <HeroStatus state={overallState} />

          {/* Error banner */}
          {loadState.state === 'error' && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
            >
              <XCircle className="size-5 shrink-0" aria-hidden="true" />
              <div>
                <div className="font-semibold">Unable to reach the health endpoint</div>
                <div className="text-compact text-danger/80">{loadState.message}</div>
              </div>
            </div>
          )}

          {/* Subsystem grid */}
          <div className="mt-4 grid grid-cols-1 gap-grid-gap sm:grid-cols-2">
            <SubsystemCard
              icon={Zap}
              label="Backend API"
              description="HTTP layer serving the dashboard, settings, and controller endpoints."
              state={apiState}
            />
            <SubsystemCard
              icon={Wifi}
              label="Live stream (WebSocket)"
              description="Realtime push channel for agent activity, tasks, and notifications."
              state={wsState}
              detail={wsDetail}
            />
            <SubsystemCard
              icon={Database}
              label="Persistence"
              description="SQLite / configured persistence backend. Writes and queries roundtrip successfully."
              state={persistenceState}
            />
            <SubsystemCard
              icon={Waves}
              label="Message bus"
              description="Internal async queue carrying inter-agent messages and engine events."
              state={busState}
            />
          </div>

          {/* Metadata footer */}
          <div className="mt-6 grid grid-cols-1 gap-3 border-t border-border pt-4 sm:grid-cols-3">
            <Metadata
              icon={Tag}
              label="Backend version"
              value={loadState.state === 'ok' ? loadState.data.version : '--'}
            />
            <Metadata
              icon={Clock}
              label="Uptime"
              value={
                loadState.state === 'ok' ? formatUptime(loadState.data.uptime_seconds) : '--'
              }
            />
            <Metadata
              icon={RefreshCw}
              label="Last probed"
              value={fetchedAtLabel ?? '--'}
            />
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Metadata({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>
  label: string
  value: string
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="size-4 text-muted-foreground" aria-hidden={true} />
      <div className="flex flex-col">
        <span className="text-compact uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span className="text-sm font-medium text-foreground">{value}</span>
      </div>
    </div>
  )
}
