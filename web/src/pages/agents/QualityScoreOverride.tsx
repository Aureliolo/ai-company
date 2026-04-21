import { useState, useCallback, useEffect, useRef } from 'react'
import { Shield, Trash2 } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { SliderField } from '@/components/ui/slider-field'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { StatPill } from '@/components/ui/stat-pill'
import { useAuth } from '@/hooks/useAuth'
import { useQualityOverridesStore } from '@/stores/quality-overrides'
import { formatDateOnly } from '@/utils/format'
import type { OverrideResponse } from '@/api/types/collaboration'

const OVERRIDE_ROLES = ['ceo', 'manager'] as const

interface QualityScoreOverrideProps {
  agentId: string
  className?: string
}

export function QualityScoreOverride({
  agentId,
  className,
}: QualityScoreOverrideProps) {
  const [override, setOverride] = useState<OverrideResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearing, setClearing] = useState(false)
  const { userRole } = useAuth()
  const canManageOverrides =
    userRole !== null &&
    (OVERRIDE_ROLES as readonly string[]).includes(userRole)

  // Form state.
  const [score, setScore] = useState(5.0)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | undefined>()
  const [expiresInDays, setExpiresInDays] = useState<number | null>(null)

  // Guard against stale responses when agentId changes. The ref is
  // updated synchronously during render so any async callback that
  // re-reads it sees the current prop even before ``useEffect``
  // commit-phase fires -- React guarantees the ref itself is stable
  // across renders, and writing to ``.current`` during render is
  // safe for this "track the latest prop" pattern. The sibling
  // ``prevAgentIdRef`` detects the prop *change* so we can reset
  // transient UI flags (spinners, open dialogs, validation errors)
  // directly during render -- React's documented "reset state when
  // props change" idiom -- instead of deferring to an effect that
  // would leave the previous agent's state visible for one frame.
  const activeAgentRef = useRef(agentId)
  activeAgentRef.current = agentId
  const prevAgentIdRef = useRef(agentId)
  if (prevAgentIdRef.current !== agentId) {
    prevAgentIdRef.current = agentId
    setSubmitting(false)
    setClearing(false)
    setClearDialogOpen(false)
    setReasonError(undefined)
  }

  const fetchOverride = useCallback(async () => {
    setLoading(true)
    setOverride(null)
    setLoadError(false)
    const result = await useQualityOverridesStore.getState().getOverride(agentId)
    if (activeAgentRef.current !== agentId) return
    if (result.kind === 'ok') {
      setOverride(result.data)
    } else if (result.kind === 'error') {
      setLoadError(true)
    }
    setLoading(false)
  }, [agentId])

  useEffect(() => {
    void fetchOverride()
  }, [fetchOverride])

  const handleSubmit = useCallback(async () => {
    if (!reason.trim()) {
      setReasonError('Reason is required')
      return
    }
    setReasonError(undefined)
    setSubmitting(true)
    // Capture the agent identity at request start so a late resolve
    // for a previous agent can't overwrite state that now belongs to
    // a different one -- matches the staleness guard in fetchOverride.
    const requestAgent = agentId
    const data = await useQualityOverridesStore.getState().setOverride(requestAgent, {
      score,
      reason: reason.trim(),
      expires_in_days: expiresInDays,
    })
    if (activeAgentRef.current !== requestAgent) {
      // Stale agent: clear the submit flag so the new agent's form
      // isn't stuck with a spinning button, but don't touch score /
      // reason / override state which now belong to the new view.
      setSubmitting(false)
      return
    }
    setSubmitting(false)
    if (data) {
      setOverride(data)
      setScore(5.0)
      setReason('')
      setExpiresInDays(null)
    }
  }, [agentId, score, reason, expiresInDays])

  const handleClear = useCallback(async (): Promise<boolean> => {
    setClearing(true)
    const requestAgent = agentId
    const ok = await useQualityOverridesStore.getState().clearOverride(requestAgent)
    if (activeAgentRef.current !== requestAgent) {
      // Stale agent: reset the busy flag so the UI for the new agent
      // isn't stuck with a spinning button, then bail out without
      // touching any state that now belongs to a different view.
      setClearing(false)
      return false
    }
    setClearing(false)
    if (!ok) return false
    setOverride(null)
    setClearDialogOpen(false)
    return true
  }, [agentId])

  if (loading) return null

  return (
    <SectionCard
      title="Quality Score Override"
      icon={Shield}
      className={className}
      action={
        override && canManageOverrides ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setClearDialogOpen(true)}
            aria-label="Clear quality override"
          >
            <Trash2 className="size-3.5" />
            Clear
          </Button>
        ) : undefined
      }
    >
      {loadError ? (
        <div className="space-y-2">
          <p className="text-sm text-danger">
            Failed to load quality override. The existing override (if
            any) is unknown -- retry before applying a new one.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void fetchOverride()}
          >
            Retry
          </Button>
        </div>
      ) : override ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-grid-gap">
            <StatPill label="Score" value={override.score.toFixed(1)} />
            <StatPill label="Applied by" value={override.applied_by} />
            <StatPill
              label="Applied"
              value={formatDateOnly(override.applied_at)}
            />
            {override.expires_at && (
              <StatPill
                label="Expires"
                value={formatDateOnly(override.expires_at)}
              />
            )}
          </div>
          <p className="text-sm text-muted-foreground">{override.reason}</p>
        </div>
      ) : canManageOverrides ? (
        <div className="space-y-3">
          <SliderField
            label="Quality Score"
            value={score}
            min={0}
            max={10}
            step={0.5}
            onChange={setScore}
            formatValue={(v) => v.toFixed(1)}
          />
          <InputField
            label="Reason"
            value={reason}
            onValueChange={setReason}
            error={reasonError}
            placeholder="Why are you overriding the quality score?"
            multiline
          />
          <SliderField
            label="Expires in (days)"
            value={expiresInDays ?? 0}
            min={0}
            max={365}
            step={1}
            // Backend requires ge=1 when set; 0 maps to null (indefinite).
            onChange={(v) => setExpiresInDays(v === 0 ? null : v)}
            formatValue={(v) => (v === 0 ? 'Indefinite' : `${v} day${v === 1 ? '' : 's'}`)}
          />
          <Button
            onClick={handleSubmit}
            disabled={submitting || !reason.trim()}
          >
            {submitting ? 'Applying...' : 'Apply Override'}
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No active quality override. Only CEO and Manager roles can
          set overrides.
        </p>
      )}

      {canManageOverrides && (
        <ConfirmDialog
          open={clearDialogOpen}
          onOpenChange={setClearDialogOpen}
          title="Clear quality override"
          description="This will remove the active quality score override. The composite scoring layers (CI signal + LLM judge) will determine the score."
          confirmLabel="Clear Override"
          variant="destructive"
          loading={clearing}
          onConfirm={handleClear}
        />
      )}
    </SectionCard>
  )
}
