import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { ACTIVE_STAGES } from '@/api/endpoints/fine-tuning'
import type { StartFineTuneRequest } from '@/api/endpoints/fine-tuning'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { useFineTuningStore } from '@/stores/fine-tuning'

import { PreflightResultPanel } from './PreflightResultPanel'

export function PipelineControlPanel() {
  const { status, preflight, loading, startRun, cancelRun, runPreflightCheck } =
    useFineTuningStore(useShallow((s) => ({
      status: s.status,
      preflight: s.preflight,
      loading: s.loading,
      startRun: s.startRun,
      cancelRun: s.cancelRun,
      runPreflightCheck: s.runPreflightCheck,
    })))
  const [sourceDir, setSourceDir] = useState('/data/documents')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [epochs, setEpochs] = useState('3')
  const [learningRate, setLearningRate] = useState('1e-5')
  const [batchSize, setBatchSize] = useState(
    String(preflight?.recommended_batch_size ?? 128),
  )

  // Clear stale preflight when sourceDir changes.
  useEffect(() => {
    useFineTuningStore.setState({ preflight: null })
  }, [sourceDir])

  const isActive = status != null && ACTIVE_STAGES.has(status.stage)

  const buildRequest = (): StartFineTuneRequest => {
    const request: StartFineTuneRequest = { source_dir: sourceDir }
    const parsedEpochs = Number(epochs)
    if (!Number.isNaN(parsedEpochs) && parsedEpochs > 0) request.epochs = parsedEpochs
    const parsedLr = Number(learningRate)
    if (!Number.isNaN(parsedLr) && parsedLr > 0) request.learning_rate = parsedLr
    const parsedBatch = Number(batchSize)
    if (!Number.isNaN(parsedBatch) && parsedBatch > 0) request.batch_size = parsedBatch
    return request
  }

  const handlePreflight = () => {
    void runPreflightCheck(buildRequest())
  }

  const handleStart = () => {
    void startRun(buildRequest())
  }

  return (
    <div className="flex flex-col gap-section-gap">
      <div className="flex items-end gap-4">
        <InputField
          label="Source Directory"
          value={sourceDir}
          onValueChange={setSourceDir}
          hint="Directory containing org documents for training"
        />
        <div className="flex gap-2 pb-1">
          <Button variant="outline" onClick={handlePreflight} disabled={loading}>
            Pre-flight Check
          </Button>
          {isActive ? (
            <Button variant="destructive" onClick={() => void cancelRun()}>
              Cancel
            </Button>
          ) : (
            <Button
              onClick={handleStart}
              disabled={loading || (preflight != null && !preflight.can_proceed)}
            >
              Start Fine-Tuning
            </Button>
          )}
        </div>
      </div>

      {preflight && <PreflightResultPanel result={preflight} />}

      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="self-start text-sm text-muted-foreground hover:text-foreground"
      >
        {showAdvanced ? 'Hide' : 'Show'} Advanced Options
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-3 gap-grid-gap rounded-lg border border-border p-card">
          <InputField label="Epochs" value={epochs} onValueChange={setEpochs} hint="Training epochs" />
          <InputField label="Learning Rate" value={learningRate} onValueChange={setLearningRate} />
          <InputField label="Batch Size" value={batchSize} onValueChange={setBatchSize} />
        </div>
      )}
    </div>
  )
}
