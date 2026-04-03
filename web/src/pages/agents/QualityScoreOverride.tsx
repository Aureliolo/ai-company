import { useState, useCallback, useEffect } from 'react'
import { Shield, Trash2 } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { SliderField } from '@/components/ui/slider-field'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { StatPill } from '@/components/ui/stat-pill'
import { useToastStore } from '@/stores/toast'
import {
  getQualityOverride,
  setQualityOverride,
  clearQualityOverride,
} from '@/api/endpoints/quality'
import { getErrorMessage } from '@/utils/errors'
import type { OverrideResponse } from '@/api/types'

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
  const [submitting, setSubmitting] = useState(false)
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearing, setClearing] = useState(false)

  // Form state.
  const [score, setScore] = useState(5.0)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | undefined>()

  const fetchOverride = useCallback(async () => {
    try {
      const data = await getQualityOverride(agentId)
      setOverride(data)
    } catch {
      setOverride(null)
    } finally {
      setLoading(false)
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
      })
      setOverride(data)
      setReason('')
      useToastStore.getState().add({ variant: 'success', title: 'Quality override applied' })
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: getErrorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }, [agentId, score, reason])

  const handleClear = useCallback(async () => {
    setClearing(true)
    try {
      await clearQualityOverride(agentId)
      setOverride(null)
      setClearDialogOpen(false)
      useToastStore.getState().add({ variant: 'success', title: 'Quality override cleared' })
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: getErrorMessage(err) })
    } finally {
      setClearing(false)
    }
  }, [agentId])

  if (loading) return null

  return (
    <SectionCard
      title="Quality Score Override"
      icon={Shield}
      className={className}
      action={
        override ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setClearDialogOpen(true)}
          >
            <Trash2 className="size-3.5" />
            Clear
          </Button>
        ) : undefined
      }
    >
      {override ? (
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
      ) : (
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
          <Button
            onClick={handleSubmit}
            disabled={submitting || !reason.trim()}
          >
            {submitting ? 'Applying...' : 'Apply Override'}
          </Button>
        </div>
      )}

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
    </SectionCard>
  )
}
