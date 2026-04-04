import { useState, useCallback, useEffect, useRef } from 'react'
import { AlertCircle, Shield, Trash2 } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { SliderField } from '@/components/ui/slider-field'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { StatPill } from '@/components/ui/stat-pill'
import { useToastStore } from '@/stores/toast'
import { useAuth } from '@/hooks/useAuth'
import {
  getQualityOverride,
  setQualityOverride,
  clearQualityOverride,
} from '@/api/endpoints/quality'
import { getErrorMessage } from '@/utils/errors'
import type { OverrideResponse } from '@/api/types'
import type { AxiosError } from 'axios'

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
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearing, setClearing] = useState(false)
  const addToast = useToastStore((s) => s.add)
  const { userRole } = useAuth()
  const canManageOverrides =
    userRole !== null &&
    (OVERRIDE_ROLES as readonly string[]).includes(userRole)

  // Form state.
  const [score, setScore] = useState(5.0)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | undefined>()
  const [expiresInDays, setExpiresInDays] = useState<number | null>(null)

  // Guard against stale responses when agentId changes.
  const activeAgentRef = useRef(agentId)

  const fetchOverride = useCallback(async () => {
    activeAgentRef.current = agentId
    setLoading(true)
    setOverride(null)
    setFetchError(null)
    try {
      const data = await getQualityOverride(agentId)
      if (activeAgentRef.current !== agentId) return
      setOverride(data)
    } catch (err) {
      if (activeAgentRef.current !== agentId) return
      const status = (err as AxiosError)?.response?.status
      if (status === 404) {
        setOverride(null)
      } else {
        setFetchError(getErrorMessage(err))
      }
    } finally {
      if (activeAgentRef.current === agentId) {
        setLoading(false)
      }
    }
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
    try {
      const data = await setQualityOverride(agentId, {
        score,
        reason: reason.trim(),
        expires_in_days: expiresInDays,
      })
      setOverride(data)
      setScore(5.0)
      setReason('')
      setExpiresInDays(null)
      addToast({ variant: 'success', title: 'Quality override applied' })
    } catch (err) {
      addToast({ variant: 'error', title: getErrorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }, [agentId, score, reason, expiresInDays, addToast])

  const handleClear = useCallback(async () => {
    setClearing(true)
    try {
      await clearQualityOverride(agentId)
      setOverride(null)
      setClearDialogOpen(false)
      addToast({ variant: 'success', title: 'Quality override cleared' })
    } catch (err) {
      addToast({ variant: 'error', title: getErrorMessage(err) })
    } finally {
      setClearing(false)
    }
  }, [agentId, addToast])

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
      {fetchError ? (
        <div className="flex items-center gap-2 text-sm text-danger">
          <AlertCircle className="size-4" />
          <span>{fetchError}</span>
        </div>
      ) : override ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-grid-gap">
            <StatPill label="Score" value={override.score.toFixed(1)} />
            <StatPill label="Applied by" value={override.applied_by} />
            <StatPill
              label="Applied"
              value={new Date(override.applied_at).toLocaleDateString()}
            />
            {override.expires_at && (
              <StatPill
                label="Expires"
                value={new Date(override.expires_at).toLocaleDateString()}
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
