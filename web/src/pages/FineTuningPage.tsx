import { useCallback, useEffect } from 'react'

import { SectionCard } from '@/components/ui/section-card'
import { useFineTuningStore } from '@/stores/fine-tuning'
import { useWebSocketStore } from '@/stores/websocket'

import { CheckpointTable } from './fine-tuning/CheckpointTable'
import { DependencyMissingBanner } from './fine-tuning/DependencyMissingBanner'
import { PipelineControlPanel } from './fine-tuning/PipelineControlPanel'
import { PipelineProgressBar } from './fine-tuning/PipelineProgressBar'
import { PipelineStepper } from './fine-tuning/PipelineStepper'
import { RunHistoryTable } from './fine-tuning/RunHistoryTable'

const ACTIVE_STAGES = new Set([
  'generating_data',
  'mining_negatives',
  'training',
  'evaluating',
  'deploying',
])

export default function FineTuningPage() {
  const { status, preflight, fetchStatus, fetchCheckpoints, fetchRuns, handleWsEvent } =
    useFineTuningStore()
  const { onChannelEvent, offChannelEvent } = useWebSocketStore()

  useEffect(() => {
    void fetchStatus()
    void fetchCheckpoints()
    void fetchRuns()
  }, [fetchStatus, fetchCheckpoints, fetchRuns])

  // Subscribe to WebSocket events for real-time updates.
  const wsHandler = useCallback(
    (event: { payload: Record<string, unknown> }) => {
      handleWsEvent(event.payload)
    },
    [handleWsEvent],
  )

  useEffect(() => {
    onChannelEvent('system', wsHandler)
    return () => offChannelEvent('system', wsHandler)
  }, [onChannelEvent, offChannelEvent, wsHandler])

  const isActive = status != null && ACTIVE_STAGES.has(status.stage)
  const hasDependencyFailure =
    preflight != null && preflight.checks.some((c) => c.name === 'dependencies' && c.status === 'fail')

  return (
    <div className="flex flex-col gap-section-gap">
      <h1 className="text-2xl font-semibold text-foreground">Embedding Fine-Tuning</h1>

      {hasDependencyFailure && <DependencyMissingBanner />}

      <SectionCard title="Pipeline Control" icon="settings">
        <PipelineControlPanel />
      </SectionCard>

      {isActive && (
        <SectionCard title="Progress" icon="activity">
          <PipelineStepper stage={status.stage} />
          <PipelineProgressBar
            stage={status.stage}
            progress={status.progress}
          />
        </SectionCard>
      )}

      <SectionCard title="Checkpoints" icon="database">
        <CheckpointTable />
      </SectionCard>

      <SectionCard title="Run History" icon="clock">
        <RunHistoryTable />
      </SectionCard>
    </div>
  )
}
