import { useCallback, useEffect } from 'react'
import { Activity, Clock, Database, Settings } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import { ACTIVE_STAGES } from '@/api/endpoints/fine-tuning'
import type { WsEvent } from '@/api/types'
import { SectionCard } from '@/components/ui/section-card'
import { useFineTuningStore } from '@/stores/fine-tuning'
import { useWebSocketStore } from '@/stores/websocket'

import { CheckpointTable } from './fine-tuning/CheckpointTable'
import { DependencyMissingBanner } from './fine-tuning/DependencyMissingBanner'
import { PipelineControlPanel } from './fine-tuning/PipelineControlPanel'
import { PipelineProgressBar } from './fine-tuning/PipelineProgressBar'
import { PipelineStepper } from './fine-tuning/PipelineStepper'
import { RunHistoryTable } from './fine-tuning/RunHistoryTable'

export default function FineTuningPage() {
  const { status, preflight, fetchStatus, fetchCheckpoints, fetchRuns, handleWsEvent } =
    useFineTuningStore(useShallow((s) => ({
      status: s.status,
      preflight: s.preflight,
      fetchStatus: s.fetchStatus,
      fetchCheckpoints: s.fetchCheckpoints,
      fetchRuns: s.fetchRuns,
      handleWsEvent: s.handleWsEvent,
    })))
  const { onChannelEvent, offChannelEvent, subscribe, unsubscribe } =
    useWebSocketStore(useShallow((s) => ({
      onChannelEvent: s.onChannelEvent,
      offChannelEvent: s.offChannelEvent,
      subscribe: s.subscribe,
      unsubscribe: s.unsubscribe,
    })))

  useEffect(() => {
    void fetchStatus()
    void fetchCheckpoints()
    void fetchRuns()
  }, [fetchStatus, fetchCheckpoints, fetchRuns])

  // Subscribe to WebSocket events for real-time updates.
  const wsHandler = useCallback(
    (event: WsEvent) => {
      handleWsEvent(event)
    },
    [handleWsEvent],
  )

  useEffect(() => {
    subscribe(['system'])
    onChannelEvent('system', wsHandler)
    return () => {
      offChannelEvent('system', wsHandler)
      unsubscribe(['system'])
    }
  }, [subscribe, unsubscribe, onChannelEvent, offChannelEvent, wsHandler])

  const isActive = status != null && ACTIVE_STAGES.has(status.stage)
  const hasDependencyFailure =
    preflight != null && preflight.checks.some((c) => c.name === 'dependencies' && c.status === 'fail')

  return (
    <div className="flex flex-col gap-section-gap">
      <h1 className="text-2xl font-semibold text-foreground">Embedding Fine-Tuning</h1>

      {hasDependencyFailure && <DependencyMissingBanner />}

      <SectionCard title="Pipeline Control" icon={Settings}>
        <PipelineControlPanel />
      </SectionCard>

      {isActive && (
        <SectionCard title="Progress" icon={Activity}>
          <PipelineStepper stage={status.stage} />
          <PipelineProgressBar
            stage={status.stage}
            progress={status.progress}
          />
        </SectionCard>
      )}

      <SectionCard title="Checkpoints" icon={Database}>
        <CheckpointTable />
      </SectionCard>

      <SectionCard title="Run History" icon={Clock}>
        <RunHistoryTable />
      </SectionCard>
    </div>
  )
}
